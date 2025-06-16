from django.urls import path, include
from django.contrib.auth import views as auth_views
import debug_toolbar

from .views import (
    HomeView, signup, LogoutView,
    TransactionListView, TransactionCreateView,
    TransactionUpdateView, TransactionDeleteView,
    transactions_json,
    CategoryListView, CategoryCreateView,
    CategoryUpdateView, CategoryDeleteView,
    category_autocomplete, tag_autocomplete,
    AccountListView, AccountCreateView,
    AccountUpdateView, AccountDeleteView,
    AccountMergeView, move_account_up,
    move_account_down, account_reorder,
    account_balance_view, delete_account_balance,
    copy_previous_balances_view,
    account_balance_export_xlsx,
    account_balance_import_xlsx,
    account_balance_template_xlsx,
    DashboardView, period_autocomplete,
    transaction_clear_cache,
    api_jwt_my_transactions, dashboard_data,
    account_balances_pivot_json, dashboard_kpis_json,
)
from core.views_reporting import proxy_report_csv_token

app_name = 'core'

urlpatterns = [
    # Home - ESTA LINHA ESTAVA EM FALTA!
    path("", HomeView.as_view(), name="home"),

    # Autenticação
    path("signup/", signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),

    # Transações
    path("transactions/", TransactionListView.as_view(), name="transaction_list"),
    path("transactions/new/", TransactionCreateView.as_view(), name="transaction_create"),
    path("transactions/<int:pk>/edit/", TransactionUpdateView.as_view(), name="transaction_update"),
    path("transactions/<int:pk>/delete/", TransactionDeleteView.as_view(), name="transaction_delete"),
    path("transactions/json/", transactions_json, name="transactions_json"),
    path("transactions/export-excel/", proxy_report_csv_token, name="transaction_export_xlsx"),
    path("transactions/import-excel/", TransactionCreateView.as_view(), name="transaction_import_xlsx"),
    path("transactions/template-excel/", TransactionCreateView.as_view(), name="transaction_import_template"),
    path("transactions/clear-cache/", transaction_clear_cache, name="transaction_clear_cache"),

    # Categorias
    path("categories/", CategoryListView.as_view(), name="category_list"),
    path("categories/new/", CategoryCreateView.as_view(), name="category_create"),
    path("categories/<int:pk>/edit/", CategoryUpdateView.as_view(), name="category_update"),
    path("categories/<int:pk>/delete/", CategoryDeleteView.as_view(), name="category_delete"),
    path("categories/autocomplete/", category_autocomplete, name="category_autocomplete"),
    path("tags/autocomplete/", tag_autocomplete, name="tag_autocomplete"),

    # Contas
    path("accounts/", AccountListView.as_view(), name="account_list"),
    path("accounts/new/", AccountCreateView.as_view(), name="account_create"),
    path("accounts/<int:pk>/edit/", AccountUpdateView.as_view(), name="account_update"),
    path("accounts/<int:pk>/delete/", AccountDeleteView.as_view(), name="account_delete"),
    path("accounts/merge/<int:source_pk>/<int:target_pk>/", AccountMergeView.as_view(), name="account_merge"),
    path("accounts/<int:pk>/up/", move_account_up, name="account_move_up"),
    path("accounts/<int:pk>/down/", move_account_down, name="account_move_down"),
    path("accounts/reorder/", account_reorder, name="account_reorder"),

    # Saldos
    path("account-balance/", account_balance_view, name="account_balance"),
    path("account-balance/delete/<int:pk>/", delete_account_balance, name="account_balance_delete"),
    path("account-balance/copy/", copy_previous_balances_view, name="account_balance_copy"),
    path("account-balance/export/", account_balance_export_xlsx, name="account_balance_export_xlsx"),
    path("account-balance/import/", account_balance_import_xlsx, name="account_balance_import_xlsx"),
    path("account-balance/template/", account_balance_template_xlsx, name="account_balance_template_xlsx"),

    # Dashboard & APIs
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("periods/autocomplete/", period_autocomplete, name="period_autocomplete"),
    path("api/jwt/my-transactions/", api_jwt_my_transactions, name="api_jwt_my_transactions"),
    path("api/dashboard-data/", dashboard_data, name="dashboard_data"),
    path("account-balances/json/", account_balances_pivot_json, name="account_balances_json"),
    path("api/dashboard-kpis/", dashboard_kpis_json, name="dashboard_kpis"),

    # Reporting CSV Token
    path("reporting/data.csv", proxy_report_csv_token, name="reporting_csv_token"),
]
