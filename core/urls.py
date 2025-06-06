# core/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from django.contrib.auth import logout as auth_logout

from .views import (
    HomeView,
    signup,
    LogoutView,

    # Transactions
    TransactionListView,
    TransactionCreateView,
    TransactionUpdateView,
    TransactionDeleteView,

    # Categories
    CategoryListView,
    CategoryCreateView,
    CategoryUpdateView,
    CategoryDeleteView,

    # Accounts
    AccountListView,
    AccountCreateView,
    AccountUpdateView,
    AccountDeleteView,
    AccountMergeView,
    move_account_up,
    move_account_down,

    # Balances
    account_balance_view,
    delete_account_balance,
    copy_previous_balances_view,
    account_reorder,
    

    #other
    category_autocomplete,
    tag_autocomplete,
    DashboardView,
)

# 👇 Logout via GET (evita erro 405 nos testes e links)
class LogoutView(RedirectView):
    pattern_name = "login"

    def get(self, request, *args, **kwargs):
        auth_logout(request)
        return super().get(request, *args, **kwargs)

urlpatterns = [
    # ───────────── Home ─────────────
    path("", HomeView.as_view(), name="home"),

    # ───────────── Auth ─────────────
    path("signup/", signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),

    # ───────── Transactions ─────────
    path("transactions/", TransactionListView.as_view(), name="transaction_list"),
    path("transactions/new/", TransactionCreateView.as_view(), name="transaction_create"),
    path("transactions/<int:pk>/edit/", TransactionUpdateView.as_view(), name="transaction_update"),
    path("transactions/<int:pk>/delete/", TransactionDeleteView.as_view(), name="transaction_delete"),

    # ────────── Categories ──────────
    path("categories/", CategoryListView.as_view(), name="category_list"),
    path("categories/new/", CategoryCreateView.as_view(), name="category_create"),
    path("categories/<int:pk>/edit/", CategoryUpdateView.as_view(), name="category_update"),
    path("categories/<int:pk>/delete/", CategoryDeleteView.as_view(), name="category_delete"),
    path("tags/autocomplete/", tag_autocomplete, name="tag_autocomplete"),

    # ─────────── Accounts ───────────
    path("accounts/", AccountListView.as_view(), name="account_list"),
    path("accounts/new/", AccountCreateView.as_view(), name="account_create"),
    path("accounts/<int:pk>/edit/", AccountUpdateView.as_view(), name="account_update"),
    path("accounts/<int:pk>/delete/", AccountDeleteView.as_view(), name="account_delete"),
    path("accounts/merge/<int:source_pk>/<int:target_pk>/", AccountMergeView.as_view(), name="account_merge"),
    path("accounts/<int:pk>/up/", move_account_up, name="account_move_up"),
    path("accounts/<int:pk>/down/", move_account_down, name="account_move_down"),
    path("accounts/reorder/", account_reorder, name="account_reorder"),
    path("categories/autocomplete/", category_autocomplete, name="category_autocomplete"),


        

    # ────────── Balances ────────────
    path("account-balance/", account_balance_view, name="account_balance"),
    path("account-balance/delete/<int:pk>/", delete_account_balance, name="account_balance_delete"),
    path("account-balance/copy/", copy_previous_balances_view, name="account_balance_copy"),


    path("dashboard/", DashboardView.as_view(), name="dashboard"),
]
