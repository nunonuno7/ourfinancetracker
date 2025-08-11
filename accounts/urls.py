from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from . import views
from .views import signup, activate, OFTPasswordResetView, DeleteAccountView

app_name = "accounts"

urlpatterns = [
    # Authentication
    path("login/",  auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/"), name="logout"),
    path("signup/", views.signup, name="signup"),
    path("activate/<uidb64>/<token>/", views.activate, name="activate"),
    path("profile/", views.profile, name="profile"),
    path("delete/", DeleteAccountView.as_view(), name="delete_account"),
    path("deleted/", TemplateView.as_view(template_name="accounts/account_deleted.html"), name="account_deleted"),

    # Password reset flow
    path("password-reset/", OFTPasswordResetView.as_view(), name="password_reset"),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url="/accounts/reset/complete/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]