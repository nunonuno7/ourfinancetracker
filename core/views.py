"""Views for the *ourfinancetracker* core app.

The file was rewritten to:
• remove duplicated imports
• share common behaviour in mix‑ins (user injection & ownership filtering)
• add a dedicated ``AccountForm`` (see ``core/forms.py``) and reuse it in
  the account CBVs
• tighten querysets so a user can only access her own data
• add docstrings and type hints for easier maintenance
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any, Dict

from django.contrib import messages
from django.contrib.auth import login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
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


class AccountCreateView(
    LoginRequiredMixin, UserInFormKwargsMixin, CreateView
):
    model = Account
    form_class = AccountForm
    template_name = "core/account_form.html"
    success_url = reverse_lazy("account_list")

    def form_valid(self, form):  # type: ignore[override]
        form.instance.user = self.request.user
        return super().form_valid(form)


class AccountUpdateView(
    OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView
):
    model = Account
    form_class = AccountForm
    template_name = "core/account_form.html"
    success_url = reverse_lazy("account_list")

################################################################################
#                           Account balance view                               #
################################################################################

@login_required
def account_balance_view(request):
    """Create/update account balances for a selected month."""

    today = date.today()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])

    qs_base = AccountBalance.objects.filter(
        account__user=request.user,
        balance_date=last_day,
    ).select_related("account", "account__account_type")

    if request.method == "POST":
        formset = AccountBalanceFormSet(
            request.POST,
            queryset=qs_base,
            user=request.user,
        )
        if formset.is_valid():
            for inst in formset.save(commit=False):
                inst.balance_date = last_day
                AccountBalance.objects.update_or_create(
                    account=inst.account,
                    balance_date=inst.balance_date,
                    defaults={
                        "reported_balance": inst.reported_balance,
                    },
                )
            for obj in formset.deleted_objects:
                obj.delete()

            _merge_duplicate_accounts(user=request.user)
            messages.success(request, "Balances saved!")
            return redirect(f"{request.path}?year={year}&month={month:02d}")
    else:
        initial_instances = list(qs_base)

        if not initial_instances:
            prev_qs = AccountBalance.objects.filter(
                account__user=request.user,
                balance_date=date(year - 1, month, monthrange(year - 1, month)[1]),
            ).select_related("account", "account__account_type")

            existing = {ab.account_id for ab in initial_instances}
            for prev in prev_qs:
                if prev.account_id not in existing:
                    prev.pk = None
                    prev.balance_date = last_day
                    initial_instances.append(prev)

        formset = AccountBalanceFormSet(
            queryset=qs_base,
            initial=[
                {
                    "account": ab.account.name,
                    "reported_balance": ab.reported_balance,
                }
                for ab in initial_instances
            ],
            user=request.user,
        )

    context = {
        "formset": formset,
        "year": year,
        "month": month,
        "selected_month": first_day,
    }
    return render(request, "core/account_balance.html", context)

def _merge_duplicate_accounts(user):
    """Procura contas duplicadas com o mesmo nome (case-insensitive) e funde tudo numa só."""
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
    """Very small wrapper around ``CustomUserCreationForm`` for now."""

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
