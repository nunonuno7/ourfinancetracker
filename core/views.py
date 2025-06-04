"""
Views for the *ourfinancetracker* core app.

The file was rewritten to:
• remove duplicated imports
• share common behaviour in mix‑ins (user injection & ownership filtering)
• add a dedicated ``AccountForm`` (see ``core/forms.py``) and reuse it in the account CBVs
• tighten querysets so a user can only access her own data
• add docstrings and type hints for easier maintenance
• introduce a MergeView for account fusion with confirmation
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any, Dict

from django.contrib import messages
from django.contrib.messages import get_messages
from django.contrib.auth import login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import QuerySet, Sum, F
from django.http import JsonResponse, Http404, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404

from django.urls import reverse_lazy, reverse
from django.utils.functional import cached_property
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.views.generic import (
    CreateView, DeleteView, ListView, RedirectView, TemplateView,
    UpdateView, View
)

from .forms import (
    AccountBalanceFormSet,
    AccountForm,
    CategoryForm,
    CustomUserCreationForm,
    TransactionForm,
)
from .models import Account, AccountBalance, Category, Transaction


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from .models import Account
from django.contrib.auth.decorators import login_required

################################################################################
#                               Menu config API                                #
################################################################################

@login_required
def menu_config(request):
    return JsonResponse({
        "username": request.user.username,
        "links": [
            {"name": "Dashboard", "url": reverse("transaction_list")},
            {"name": "New Transaction", "url": reverse("transaction_create")},
            {"name": "Categories", "url": reverse("category_list")},
            {"name": "Account Balances", "url": reverse("account_balance")},
        ]
    })


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

    def get_queryset(self) -> QuerySet:
        return (
            super().get_queryset()
            .filter(user=self.request.user)
            .order_by("-date")
        )


class TransactionCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class TransactionUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list")


class TransactionDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Transaction
    template_name = "core/confirms/transaction_confirm_delete.html"
    success_url = reverse_lazy("transaction_list")

################################################################################
#                               Category views                                 #
################################################################################


class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = "core/category_list.html"
    context_object_name = "categories"

    def get_queryset(self) -> QuerySet:
        return super().get_queryset().filter(user=self.request.user)  # type: ignore[misc]


class CategoryCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "core/category_form.html"
    success_url = reverse_lazy("category_list")

    def form_valid(self, form):  # type: ignore[override]
        form.instance.user = self.request.user
        return super().form_valid(form)


class CategoryUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "core/category_form.html"
    success_url = reverse_lazy("category_list")


class CategoryDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Category
    template_name = "core/confirms/category_confirm_delete.html"
    success_url = reverse_lazy("category_list")

################################################################################
#                               Account views                                  #
################################################################################





class AccountListView(LoginRequiredMixin, ListView):
    model = Account
    template_name = "core/account_list.html"
    context_object_name = "accounts"

    def get_queryset(self) -> QuerySet:
        return (
            super()
            .get_queryset()
            .filter(user=self.request.user)
            .order_by("position", "name")
        )
# views.py
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Protege o acesso à relação OneToOne
        default_currency = getattr(user, "settings", None)
        context["default_currency"] = getattr(default_currency, "default_currency", "€")

        # (Resto da lógica permanece igual)
        return context


class AccountCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    model = Account
    form_class = AccountForm
    template_name = "core/account_form.html"
    success_url = reverse_lazy("account_list")

    def form_valid(self, form):
        existing = form.find_duplicate()

        if existing:
            new_account = form.save(commit=False)
            new_account.user = self.request.user
            new_account.save()

            return redirect(
                "account_merge",
                source_pk=new_account.pk,
                target_pk=existing.pk
            )

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
        # Verifica se há outra conta com o mesmo nome (ignorando maiúsculas/minúsculas)
        new_name = form.cleaned_data["name"].strip()
        existing = Account.objects.filter(
            user=self.request.user,
            name__iexact=new_name
        ).exclude(pk=self.object.pk).first()

        if existing:
            # Guarda o objeto editado para depois fundir
            form.save(commit=False)  # não guardamos já no DB
            return redirect(
                "account_merge",
                source_pk=self.object.pk,
                target_pk=existing.pk
            )

        try:
            self.object = form.save()
        except ValidationError as e:
            form.add_error(None, e.message)
            return self.form_invalid(form)

        return super().form_valid(form)


class AccountDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Account
    template_name = "core/confirms/account_confirm_delete.html"
    success_url = reverse_lazy("account_list")

    def dispatch(self, request, *args, **kwargs):
        account = self.get_object()
        if account.name.lower() == "cash":
            return HttpResponseForbidden("Default account cannot be deleted.")
        return super().dispatch(request, *args, **kwargs)


class AccountMergeView(OwnerQuerysetMixin, View):
    template_name = "core/confirms/account_confirm_merge.html"
    success_url = reverse_lazy("account_list")

    def get(self, request, *args, **kwargs):
        self.source = self.get_source_account()
        self.target = self.get_target_account()

        if not self.source or not self.target:
            messages.error(request, "Accounts not found for merging.")
            return redirect("account_list")

        return render(request, self.template_name, {
            "source": self.source,
            "target": self.target,
        })


    def post(self, request, *args, **kwargs):
        target = self.get_target_account()
        source = self.get_source_account()

        if not source or not target or source == target:
            messages.error(request, "Invalid merge.")
            return redirect("account_list")

        # Reconciliar saldos duplicados
        for bal in AccountBalance.objects.filter(account=source):
            existing = AccountBalance.objects.filter(
                account=target, year=bal.year, month=bal.month
            ).first()

            if existing:
                # Exemplo: somar os saldos
                existing.reported_balance += bal.reported_balance
                existing.save()
                bal.delete()
            else:
                bal.account = target
                bal.save()

        source.delete()
        messages.success(request, f"Merged account '{source.name}' into '{target.name}'")
        return redirect(self.success_url)


    def get_source_account(self):
        return Account.objects.filter(user=self.request.user, pk=self.kwargs["source_pk"]).first()

    def get_target_account(self):
        return Account.objects.filter(user=self.request.user, pk=self.kwargs["target_pk"]).first()

################################################################################
#                           Account balance view                               #
################################################################################

@login_required
def account_balance_view(request):
    list(get_messages(request))
    today = date.today()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    # 🧼 Limpa mensagens pendentes (ex: vindas do copy)
    if request.method == "GET":
        list(get_messages(request))

    qs_base = AccountBalance.objects.filter(
        account__user=request.user,
        year=year,
        month=month
    ).select_related("account", "account__account_type")

    if request.method == "POST":
        formset = AccountBalanceFormSet(request.POST, queryset=qs_base, user=request.user)

        if formset.is_valid():
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

            _merge_duplicate_accounts(request.user)

            messages.success(request, "Balances saved!")
            return redirect(f"{request.path}?year={year}&month={month:02d}")

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



def _merge_duplicate_accounts(user):
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

    def get(self, request, *args, **kwargs):
        auth_logout(request)
        return super().get(request, *args, **kwargs)


class HomeView(TemplateView):
    template_name = "core/home.html"


@require_POST
@csrf_exempt
@login_required
def delete_account_balance(request, pk):
    try:
        obj = AccountBalance.objects.get(pk=pk, account__user=request.user)
        obj.delete()
        return JsonResponse({"success": True})
    except AccountBalance.DoesNotExist:
        return JsonResponse({"success": False, "error": "Not found"}, status=404)


@require_GET
@login_required
def copy_previous_balances_view(request):
    """Copies balances from the previous month if they do not already exist."""
    year = int(request.GET.get("year"))
    month = int(request.GET.get("month"))

    # Calcula mês anterior
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year

    created_count = 0
    user = request.user

    previous_balances = AccountBalance.objects.filter(
        account__user=user,
        year=prev_year,
        month=prev_month
    ).select_related("account")

    for bal in previous_balances:
        exists = AccountBalance.objects.filter(
            account=bal.account,
            year=year,
            month=month
        ).exists()

        if not exists:
            AccountBalance.objects.create(
                account=bal.account,
                year=year,
                month=month,
                reported_balance=bal.reported_balance
            )
            created_count += 1

    return JsonResponse({"success": True, "created": created_count})

@login_required
def move_account_up(request, pk):
    account = get_object_or_404(Account, pk=pk, user=request.user)
    above = Account.objects.filter(user=request.user, position__lt=account.position).order_by("-position").first()
    if above:
        account.position, above.position = above.position, account.position
        account.save()
        above.save()
    return redirect("account_list")

@login_required
def move_account_down(request, pk):
    account = get_object_or_404(Account, pk=pk, user=request.user)
    below = Account.objects.filter(user=request.user, position__gt=account.position).order_by("position").first()
    if below:
        account.position, below.position = below.position, account.position
        account.save()
        below.save()
    return redirect("account_list")

@csrf_exempt  # Ou substitui por @login_required + token se estiver a funcionar corretamente
@login_required
def account_reorder(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            order = data.get("order", [])
            for item in order:
                Account.objects.filter(pk=item["id"], user=request.user).update(position=item["position"])
            return JsonResponse({"status": "ok"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "invalid method"}, status=405)