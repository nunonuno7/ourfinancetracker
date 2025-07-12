from django.urls import path
from django.contrib.auth import views as auth_views

from . import views
from .views import (
    # Home & Auth
    HomeView, signup, LogoutView,
    # Transactions
    TransactionCreateView,
    TransactionUpdateView, TransactionDeleteView,
    transactions_json, import_transactions_xlsx,
    import_transactions_template, transaction_clear_cache,
    export_transactions_xlsx, transaction_bulk_update,
    transaction_bulk_duplicate, transaction_bulk_delete,
    clear_session_flag, transaction_list_v2, transactions_json_v2,
    transactions_totals_v2,
    # Categories & Tags
    CategoryListView, CategoryCreateView,
    CategoryUpdateView, CategoryDeleteView,
    category_autocomplete, tag_autocomplete,
    # Accounts
    AccountListView, AccountCreateView,
    AccountUpdateView, AccountDeleteView,
    AccountMergeView, move_account_up,
    move_account_down, account_reorder,
    # Account Balances
    account_balance_view, delete_account_balance,
    copy_previous_balances_view, account_balance_export_xlsx,
    account_balance_import_xlsx, account_balance_template_xlsx,
    # Dashboard & APIs
    DashboardView, period_autocomplete, menu_config,
    api_jwt_my_transactions, dashboard_data,
    account_balances_pivot_json, dashboard_kpis_json,
    financial_analysis_json, sync_system_adjustments,
    clear_transaction_cache_view,
    # Transaction Estimation
    estimate_transaction_view,
    get_estimation_summaries,
    estimate_transaction_for_period,
    delete_estimated_transaction,
    delete_estimated_transaction_by_period,
)

from .views_reporting import proxy_report_csv_token

urlpatterns = [
    # Home
    path("", HomeView.as_view(), name="home"),

    # Authentication
    path("signup/", signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),

    # Dashboard
    path("dashboard/", DashboardView.as_view(), name="dashboard"),

    # Transactions
    path("transactions/", transaction_list_v2, name="transaction_list"),  # Alias for backward compatibility
    path("transactions-v2/", transaction_list_v2, name="transaction_list_v2"),
    path("transactions/new/", TransactionCreateView.as_view(), name="transaction_create"),
    path("transactions/<int:pk>/edit/", TransactionUpdateView.as_view(), name="transaction_update"),
    path("transactions/<int:pk>/delete/", TransactionDeleteView.as_view(), name="transaction_delete"),
    path("transactions/json/", transactions_json, name="transactions_json"),
    path("transactions/json-v2/", transactions_json_v2, name="transactions_json_v2"),
    path("transactions/totals-v2/", transactions_totals_v2, name="transactions_totals_v2"),
    path("transactions/export-excel/", export_transactions_xlsx, name="transaction_export_xlsx"),
    path("transactions/import-excel/", import_transactions_xlsx, name="transaction_import_xlsx"),
    path("transactions/import/template/", import_transactions_template, name="import_transactions_template_xlsx"),
    path("transactions/clear-cache/", transaction_clear_cache, name="transaction_clear_cache"),
    path("transactions/clear-session-flag/", clear_session_flag, name="clear_session_flag"),

    # Bulk operations
    path('transactions/bulk-update/', transaction_bulk_update, name='transaction_bulk_update'),
    path('transactions/bulk-duplicate/', transaction_bulk_duplicate, name='transaction_bulk_duplicate'),
    path('transactions/bulk-delete/', transaction_bulk_delete, name='transaction_bulk_delete'),

    # Estimation endpoints
    path('transactions/estimate/', views.estimate_transaction_view, name='estimate_transaction'),
    path('transactions/estimate/period/', views.estimate_transaction_for_period, name='estimate_transaction_for_period'),
    path('transactions/estimate/summaries/', views.get_estimation_summaries, name='get_estimation_summaries'),
    path('transactions/estimate/years/', views.get_available_years, name='get_available_years'),
    path('transactions/estimate/<int:transaction_id>/delete/', views.delete_estimated_transaction, name='delete_estimated_transaction'),
    path('transactions/estimate/period/<int:period_id>/delete/', views.delete_estimated_transaction_by_period, name='delete_estimated_transaction_by_period'),

    # Categories
    path("categories/", CategoryListView.as_view(), name="category_list"),
    path("categories/new/", CategoryCreateView.as_view(), name="category_create"),
    path("categories/<int:pk>/edit/", CategoryUpdateView.as_view(), name="category_update"),
    path("categories/<int:pk>/delete/", CategoryDeleteView.as_view(), name="category_delete"),
    path("categories/autocomplete/", category_autocomplete, name="category_autocomplete"),

    # Tags
    path("tags/autocomplete/", tag_autocomplete, name="tag_autocomplete"),

    # Accounts
    path("accounts/", AccountListView.as_view(), name="account_list"),
    path("accounts/new/", AccountCreateView.as_view(), name="account_create"),
    path("accounts/<int:pk>/edit/", AccountUpdateView.as_view(), name="account_update"),
    path("accounts/<int:pk>/delete/", AccountDeleteView.as_view(), name="account_delete"),
    path("accounts/<int:source_pk>/merge/<int:target_pk>/", AccountMergeView.as_view(), name="account_merge"),
    path("accounts/<int:pk>/up/", move_account_up, name="account_move_up"),
    path("accounts/<int:pk>/down/", move_account_down, name="account_move_down"),
    path("accounts/reorder/", account_reorder, name="account_reorder"),

    # Account Balances
    path("account-balance/", account_balance_view, name="account_balance"),
    path("account-balance/delete/<int:pk>/", delete_account_balance, name="delete_account_balance"),
    path("account-balance/copy/", copy_previous_balances_view, name="copy_previous_balances"),
    path("account-balance/export-excel/", account_balance_export_xlsx, name="account_balance_export_xlsx"),
    path("account-balance/import-excel/", account_balance_import_xlsx, name="account_balance_import_xlsx"),
    path("account-balance/template/", account_balance_template_xlsx, name="account_balance_template_xlsx"),

    # API endpoints
    path("api/periods/autocomplete/", period_autocomplete, name="period_autocomplete"),
    path("api/menu-config/", menu_config, name="menu_config"),
    path("api/jwt/my-transactions/", api_jwt_my_transactions, name="api_jwt_my_transactions"),
    path("api/dashboard-data/", dashboard_data, name="dashboard_data"),
    path("dashboard/kpis/", dashboard_kpis_json, name="dashboard_kpis_json"),
    path("financial-analysis/json/", financial_analysis_json, name="financial_analysis_json"),
    path("account-balances/json/", account_balances_pivot_json, name="account_balances_json"),
    path("api/sync-adjustments/", sync_system_adjustments, name="sync_system_adjustments"),
    path("account-balances/pivot-json/", account_balances_pivot_json, name="account_balances_pivot_json"),

    # Clear cache
    path("clear-cache/", clear_transaction_cache_view, name="clear_transaction_cache"),

    # Reporting (token-based)
    path("reporting/data.csv", proxy_report_csv_token, name="reporting_csv_token"),
]