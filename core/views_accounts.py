"""Account views."""

import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db import connection
from django.db import transaction as db_transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import AccountForm, UserInFormKwargsMixin
from .mixins import OwnerQuerysetMixin, SimpleDeleteFlowMixin
from .models import Account, DatePeriod, Transaction

logger = logging.getLogger(__name__)


class AccountListView(OwnerQuerysetMixin, ListView):
    """List accounts for current user."""

    model = Account
    template_name = "core/account_list.html"
    context_object_name = "accounts"
    paginate_by = 50

    def get_queryset(self):
        """Optimize queryset with select_related for foreign keys."""
        queryset = (
            super()
            .get_queryset()
            .select_related("account_type", "currency")
            .prefetch_related("balances__period")
        )

        search_query = self.request.GET.get("q", "").strip()
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)

        return queryset.order_by("position", "name")

    def get_context_data(self, **kwargs):
        """Add optimized context data."""
        context = super().get_context_data(**kwargs)

        accounts = context["accounts"]
        account_type_totals = {}
        default_currency = "EUR"
        latest_period = DatePeriod.objects.order_by("-year", "-month").first()

        if latest_period and accounts:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT at.name,
                           COALESCE(SUM(ab.reported_balance), 0) as total_balance,
                           c.code as currency
                    FROM core_accounttype at
                    LEFT JOIN core_account a ON a.account_type_id = at.id AND a.user_id = %s
                    LEFT JOIN core_currency c ON a.currency_id = c.id
                    LEFT JOIN core_accountbalance ab ON ab.account_id = a.id AND ab.period_id = %s
                    GROUP BY at.name, c.code
                    HAVING COALESCE(SUM(ab.reported_balance), 0) != 0
                    ORDER BY at.name
                """,
                    [self.request.user.id, latest_period.id],
                )

                results = cursor.fetchall()
                for account_type, balance, currency in results:
                    if balance:
                        currency_symbol = currency or default_currency
                        account_type_totals[account_type] = (
                            f"{balance:,.0f} {currency_symbol}"
                        )

        context["account_type_totals"] = account_type_totals
        context["default_currency"] = default_currency

        return context


class AccountCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    """Create new account."""

    model = Account
    form_class = AccountForm
    template_name = "core/account_form.html"
    success_url = reverse_lazy("account_list")


class AccountUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    """Update account."""

    model = Account
    form_class = AccountForm
    template_name = "core/account_form.html"
    success_url = reverse_lazy("account_list")


class AccountDeleteView(SimpleDeleteFlowMixin, OwnerQuerysetMixin, DeleteView):
    """Delete account."""

    model = Account
    template_name = "core/confirms/account_confirm_delete.html"
    success_url = reverse_lazy("account_list")
    success_message = 'Account "{object}" deleted successfully.'


class AccountMergeView(LoginRequiredMixin, View):
    """Merge two accounts."""

    template_name = "core/confirms/account_confirm_merge.html"

    def get(self, request, source_pk, target_pk):
        source = get_object_or_404(Account, pk=source_pk, user=request.user)
        target = get_object_or_404(Account, pk=target_pk, user=request.user)
        return render(request, self.template_name, {"source": source, "target": target})

    def post(self, request, source_pk, target_pk):
        source = get_object_or_404(Account, pk=source_pk, user=request.user)
        target = get_object_or_404(Account, pk=target_pk, user=request.user)

        Transaction.objects.filter(account=source).update(account=target)
        source.delete()

        messages.success(
            request, f'Account "{source.name}" merged into "{target.name}"'
        )
        return redirect("account_list")


@login_required
def move_account_up(request, pk):
    """Move account up in order."""
    get_object_or_404(Account, pk=pk, user=request.user)
    return redirect("account_list")


@login_required
def move_account_down(request, pk):
    """Move account down in order."""
    get_object_or_404(Account, pk=pk, user=request.user)
    return redirect("account_list")


@login_required
def account_reorder(request):
    """Reorder accounts via AJAX."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            order_list = data.get("order", [])

            logger.debug(
                f"Reordering accounts for user {request.user.id}: {order_list}"
            )

            with db_transaction.atomic():
                for index, item in enumerate(order_list):
                    account_id = item.get("id")

                    if account_id:
                        updated_count = Account.objects.filter(
                            id=account_id, user=request.user
                        ).update(position=index)

                        if updated_count:
                            logger.debug(
                                f"Updated account {account_id} to position {index}"
                            )
                        else:
                            logger.warning(
                                f"Account {account_id} not found or not owned by user {request.user.id}"
                            )

            cache.delete(f"account_balance_{request.user.id}")
            cache.delete(f"account_summary_{request.user.id}")

            logger.info(f"Account order updated for user {request.user.id}")
            return JsonResponse(
                {"success": True, "message": "Account order updated successfully"}
            )

        except Exception as exc:
            logger.error(f"Error reordering accounts for user {request.user.id}: {exc}")
            return JsonResponse({"success": False, "error": str(exc)})

    return JsonResponse({"success": False, "error": "POST method required"})


def _merge_duplicate_accounts(user):
    """Optimized helper to merge duplicate accounts by name."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT LOWER(TRIM(name)) as normalized_name,
                   array_agg(id ORDER BY created_at) as account_ids,
                   COUNT(*) as count
            FROM core_account
            WHERE user_id = %s
            GROUP BY LOWER(TRIM(name))
            HAVING COUNT(*) > 1
        """,
            [user.id],
        )

        duplicates = cursor.fetchall()

        if not duplicates:
            return

        logger.info(
            f"Found {len(duplicates)} sets of duplicate accounts for user {user.id}"
        )

        for normalized_name, account_ids, count in duplicates:
            primary_id = account_ids[0]
            duplicate_ids = account_ids[1:]

            logger.debug(f"Merging accounts {duplicate_ids} into {primary_id}")

            cursor.execute(
                """
                UPDATE core_accountbalance
                SET account_id = %s
                WHERE account_id = ANY(%s)
            """,
                [primary_id, duplicate_ids],
            )

            cursor.execute(
                """
                UPDATE core_transaction
                SET account_id = %s
                WHERE account_id = ANY(%s)
            """,
                [primary_id, duplicate_ids],
            )

            cursor.execute(
                """
                DELETE FROM core_account
                WHERE id = ANY(%s)
            """,
                [duplicate_ids],
            )

        logger.info(f"Account merge completed for user {user.id}")


__all__ = [
    "AccountListView",
    "AccountCreateView",
    "AccountUpdateView",
    "AccountDeleteView",
    "AccountMergeView",
    "move_account_up",
    "move_account_down",
    "account_reorder",
    "_merge_duplicate_accounts",
]
