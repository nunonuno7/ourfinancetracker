"""Compatibility layer and lightweight views kept in ``core.views``."""

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from .models import Account, Category, Transaction, User, UserSettings
from .tasks import import_transactions_task
from .views_account_balance import (
    account_balance_export_xlsx,
    account_balance_import_xlsx,
    account_balance_template_xlsx,
    account_balance_view,
    copy_previous_balances_view,
    delete_account_balance,
)
from .views_accounts import (
    AccountCreateView,
    AccountDeleteView,
    AccountListView,
    AccountMergeView,
    AccountUpdateView,
    account_reorder,
    move_account_down,
    move_account_up,
)
from .views_categories import (
    CategoryCreateView,
    CategoryDeleteView,
    CategoryListView,
    CategoryUpdateView,
    category_autocomplete,
    tag_autocomplete,
)
from .views_dashboard import (
    DashboardView,
    account_balances_pivot_json,
    api_jwt_my_transactions,
    dashboard,
    dashboard_data,
    dashboard_export,
    dashboard_goals_json,
    dashboard_insights_json,
    dashboard_kpis_json,
    dashboard_returns_json,
    dashboard_spending_by_category_json,
    financial_analysis_json,
    menu_config,
    period_autocomplete,
    sync_system_adjustments,
)
from .views_estimation import (
    delete_estimated_transaction,
    delete_estimated_transaction_by_period,
    estimate_transaction_for_period,
    estimate_transaction_page,
    get_available_years,
    get_estimation_summaries,
    transaction_estimate,
)
from .views_import_export import (
    export_data_xlsx,
    export_transactions_xlsx,
    import_transactions_template,
    import_transactions_xlsx,
    task_status,
)
from .views_recurring import (
    RecurringTransactionCreateView,
    RecurringTransactionDeleteView,
    RecurringTransactionListView,
    RecurringTransactionUpdateView,
)
from .views_transactions import (
    clear_session_flag,
    transaction_list_v2,
    transactions_json_v2,
    transactions_totals_v2,
)
from .views_transactions_legacy import (
    TransactionCreateView,
    TransactionDeleteView,
    TransactionUpdateView,
    clear_transaction_cache_view,
    transaction_bulk_delete,
    transaction_bulk_duplicate,
    transaction_bulk_update,
    transaction_clear_cache,
    transactions_json,
)


class HomeView(TemplateView):
    """Home page view."""

    template_name = "core/home.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Total users (rounded to tens)
        total_users = User.objects.count()
        context["total_users"] = total_users // 10

        # Total transactions (rounded to thousands)
        total_transactions = Transaction.objects.count()
        context["total_transactions"] = total_transactions // 1000

        # Total accounts (rounded to tens)
        total_accounts = Account.objects.count()
        context["total_accounts"] = total_accounts // 10

        # Total categories (rounded to tens)
        total_categories = Category.objects.count()
        context["total_categories"] = total_categories // 10

        return context


# ==============================================================================
# HEALTH AND KPI VIEWS
# ==============================================================================


def healthz(_request):
    """
    Lightweight health endpoint used by external monitors to keep the app warm.
    Must not touch the database or perform expensive work.
    """
    response = HttpResponse("ok", content_type="text/plain", status=200)
    # Avoid intermediary caches; make sure the request reaches the app
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@require_http_methods(["GET"])
@login_required
def kpi_goals_get(request):
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
    return JsonResponse({"kpi_goals": settings_obj.kpi_goals or {}})


@require_http_methods(["POST"])
@login_required
def kpi_goals_update(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    key = data.get("kpi_key")
    try:
        goal = float(data.get("goal"))
    except (TypeError, ValueError):
        goal = 0
    mode = data.get("mode", "closest")
    if not key:
        return JsonResponse({"error": "kpi_key required"}, status=400)
    if mode not in {"higher", "lower", "closest"}:
        mode = "closest"
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
    goals = settings_obj.kpi_goals or {}
    goals[key] = {"goal": goal, "mode": mode}
    settings_obj.kpi_goals = goals
    settings_obj.save(update_fields=["kpi_goals"])
    return JsonResponse({"kpi_goals": goals})


__all__ = [
    "AccountCreateView",
    "AccountDeleteView",
    "AccountListView",
    "AccountMergeView",
    "AccountUpdateView",
    "CategoryCreateView",
    "CategoryDeleteView",
    "CategoryListView",
    "CategoryUpdateView",
    "DashboardView",
    "HomeView",
    "RecurringTransactionCreateView",
    "RecurringTransactionDeleteView",
    "RecurringTransactionListView",
    "RecurringTransactionUpdateView",
    "TransactionCreateView",
    "TransactionDeleteView",
    "TransactionUpdateView",
    "account_balance_export_xlsx",
    "account_balance_import_xlsx",
    "account_balance_template_xlsx",
    "account_balance_view",
    "account_balances_pivot_json",
    "account_reorder",
    "api_jwt_my_transactions",
    "category_autocomplete",
    "clear_session_flag",
    "clear_transaction_cache_view",
    "copy_previous_balances_view",
    "dashboard",
    "dashboard_data",
    "dashboard_export",
    "dashboard_goals_json",
    "dashboard_insights_json",
    "dashboard_kpis_json",
    "dashboard_returns_json",
    "dashboard_spending_by_category_json",
    "delete_account_balance",
    "delete_estimated_transaction",
    "delete_estimated_transaction_by_period",
    "estimate_transaction_for_period",
    "estimate_transaction_page",
    "export_data_xlsx",
    "export_transactions_xlsx",
    "financial_analysis_json",
    "get_available_years",
    "get_estimation_summaries",
    "healthz",
    "import_transactions_task",
    "import_transactions_template",
    "import_transactions_xlsx",
    "kpi_goals_get",
    "kpi_goals_update",
    "menu_config",
    "move_account_down",
    "move_account_up",
    "period_autocomplete",
    "sync_system_adjustments",
    "tag_autocomplete",
    "task_status",
    "transaction_bulk_delete",
    "transaction_bulk_duplicate",
    "transaction_bulk_update",
    "transaction_clear_cache",
    "transaction_estimate",
    "transaction_list_v2",
    "transactions_json",
    "transactions_json_v2",
    "transactions_totals_v2",
]
