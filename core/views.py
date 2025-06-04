"""""Views for the *ourfinancetracker* core app.

The file was rewritten to:
• remove duplicated imports
• share common behaviour in mix‑ins (user injection & ownership filtering)
• add a dedicated ``AccountForm`` (see ``core/forms.py``) and reuse it in
  the account CBVs
• tighten querysets so a user can only access her own data
• add docstrings and type hints for easier maintenance
"""
from __future__ import annotations

from django.core.exceptions import ValidationError

from calendar import monthrange
from datetime import date
from typing import Any, Dict
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth import login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.http import JsonResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    RedirectView,
    TemplateView,
    UpdateView,
)

from .forms import (
    AccountBalanceFormSet,
    AccountForm,
    CategoryForm,
    CustomUserCreationForm,
    TransactionForm,
)
from .models import Account, AccountBalance, Category, Transaction
from django.http import HttpResponseForbidden

################################################################################
#                               Shared mix‑ins                                 #
################################################################################


class UserInFormKwargsMixin:
    """Injects the current *request.user* into ModelForm kwargs."""

    def get_form_kwargs(self) -> Dict[str, Any]:  # type: ignore[override]
        kwargs: Dict[str, Any] = super().get_form_kwargs()  # type: ignore[misc]
        kwargs["user"] = self.request.user
        return kwargs


class OwnerQuerysetMixin(LoginRequiredMixin):
    """Limits queryset to objects owned by the current user."""

    def get_queryset(self) -> QuerySet:  # type: ignore[override]
        qs: QuerySet = super().get_queryset()  # type: ignore[misc]
        return qs.filter(user=self.request.user)

################################################################################
#                             Transaction views                                #
################################################################################


class TransactionListView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = "core/transaction_list.html"
    context_object_name = "transactions"

    def get_queryset(self) -> QuerySet:  # noqa: D401
        return (
            super()
            .get_queryset()  # type: ignore[misc]
            .filter(user=self.request.user)
            .order_by("-date")
        )


class TransactionCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list")

    def form_valid(self, form):  # type: ignore[override]
        form.instance.user = self.request.user
        return super().form_valid(form)


class TransactionUpdateView(
    OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView
):
    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list")


class TransactionDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Transaction
    template_name = "core/transaction_confirm_delete.html"
    success_url = reverse_lazy("transaction_list")

################################################################################
#                               Category views                                 #
################################################################################


class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = "core/category_list.html"
    context_object_name = "categories"

    def get_queryset(self) -> QuerySet:  # noqa: D401
        return super().get_queryset().filter(user=self.request.user)  # type: ignore[misc]


class CategoryCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "core/category_form.html"
    success_url = reverse_lazy("category_list")

    def form_valid(self, form):  # type: ignore[override]
        form.instance.user = self.request.user
        return super().form_valid(form)


class CategoryUpdateView(
    OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView
):
    model = Category
    form_class = CategoryForm
    template_name = "core/category_form.html"
    success_url = reverse_lazy("category_list")


class CategoryDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Category
    template_name = "core/category_confirm_delete.html"
    success_url = reverse_lazy("category_list")

################################################################################
#                               Account views                                  #
################################################################################


class AccountListView(LoginRequiredMixin, ListView):
    model = Account
    template_name = "core/account_list.html"
    context_object_name = "accounts"

    def get_queryset(self) -> QuerySet:  # noqa: D401
        return super().get_queryset().filter(user=self.request.user)  # type: ignore[misc]


class AccountCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    model = Account
    form_class = AccountForm
    template_name = "core/account_form.html"
    success_url = reverse_lazy("account_list")

    def form_valid(self, form):
        try:
            self.object = form.save()
        except ValidationError as e:
            form.add_error(None, e.message)
            return self.form_invalid(form)
        return super().form_valid(form)



class AccountUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    model = Account
    form_class = AccountForm
    template_name = "core/account_form.html"
    success_url = reverse_lazy("account_list")

    def form_valid(self, form):
        try:
            self.object = form.save()
        except ValidationError as e:
            form.add_error(None, e.message)
            return self.form_invalid(form)
        return super().form_valid(form)

################################################################################
#                           Account balance view                               #
################################################################################

@login_required
def account_balance_view(request):
    today = date.today()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    qs_base = AccountBalance.objects.filter(
        account__user=request.user,
        year=year,
        month=month
    ).select_related("account", "account__account_type")

    if request.method == "POST":
        formset = AccountBalanceFormSet(request.POST, queryset=qs_base, user=request.user)

        if formset.is_valid():
            print("✅ DEBUG: cleaned_data das linhas submetidas:")
            for form in formset:
                print(form.cleaned_data)

            instances = formset.save(commit=False)

            for form in formset:
                if form.cleaned_data.get("DELETE"):
                    continue

                inst = form.save(commit=False)
                inst.year = year
                inst.month = month

                if inst.account.user_id is None:
                    inst.account.user = request.user
                    inst.account.save()


                existing = AccountBalance.objects.filter(
                    account=inst.account,
                    year=inst.year,
                    month=inst.month
                ).first()

                if existing:
                    existing.reported_balance = inst.reported_balance
                    existing.save()
                else:
                    inst.save()

                print(f"💾 Guardado: {inst.account.name} = {inst.reported_balance}")

            _merge_duplicate_accounts(request.user)

            messages.success(request, "Balances saved!")
            return redirect(f"{request.path}?year={year}&month={month:02d}")

        else:
            print("❌ Formset inválido — erros:")
            for i, form in enumerate(formset):
                if form.errors:
                    print(f"[form {i}] {form.errors}")
            messages.error(request, "Erro ao guardar os saldos. Verifica os campos.")

    else:
        formset = AccountBalanceFormSet(queryset=qs_base, user=request.user)

    context = {
        "formset": formset,
        "year": year,
        "month": month,
        "selected_month": date(year, month, 1),
    }
    return render(request, "core/account_balance.html", context)


@require_POST
@login_required
def delete_account_balance(request):
    balance_id = request.POST.get("id")
    if not balance_id:
        return JsonResponse({"error": "Missing balance ID."}, status=400)

    try:
        obj = AccountBalance.objects.get(pk=balance_id, account__user=request.user)
    except AccountBalance.DoesNotExist:
        raise Http404("AccountBalance not found.")

    obj.delete()
    return JsonResponse({"success": True})


def _merge_duplicate_accounts(user):
    from .models import Account, AccountBalance

    seen = {}
    for acc in Account.objects.filter(user=user).order_by("name"):
        name = acc.name.strip().lower()
        if name in seen:
            primary = seen[name]
            AccountBalance.objects.filter(account=acc).update(account=primary)
            acc.delete()
        else:
            seen[name] = acc

################################################################################
#                               Misc views                                     #
################################################################################

def signup(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("transaction_list")
    else:
        form = CustomUserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


class LogoutView(RedirectView):
    pattern_name = "login"

    def get(self, request, *args, **kwargs):  # noqa: D401
        auth_logout(request)
        return super().get(request, *args, **kwargs)


class HomeView(TemplateView):
    template_name = "core/home.html"


@require_POST
@csrf_exempt  # se quiseres evitar erro CSRF num POST via fetch, ou substitui por @csrf_protect com token no JS
@login_required
def delete_account_balance(request, pk):
    try:
        obj = AccountBalance.objects.get(pk=pk, account__user=request.user)
        obj.delete()
        return JsonResponse({"success": True})
    except AccountBalance.DoesNotExist:
        return JsonResponse({"success": False, "error": "Not found"}, status=404)
    

class AccountDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Account
    template_name = "core/account_confirm_delete.html"
    success_url = reverse_lazy("account_list")

    def dispatch(self, request, *args, **kwargs):
        account = self.get_object()
        if account.name.lower() == "cash":
            return HttpResponseForbidden("Default account cannot be deleted.")
        return super().dispatch(request, *args, **kwargs)