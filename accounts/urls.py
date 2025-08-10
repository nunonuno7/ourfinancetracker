from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from . import views

app_name = "accounts"  # Important for namespace support

urlpatterns = [
    # Authentication
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/"), name="logout"),
    path("signup/", views.signup, name="signup"),
    path("activate/<uidb64>/<token>/", views.activate, name="activate"),

    # Password Reset URLs
    path("password-reset/",
         views.CustomPasswordResetView.as_view(
             template_name="accounts/password_reset.html",
             email_template_name="accounts/emails/password_reset_email.html",
             html_email_template_name="accounts/emails/password_reset_email.html",
             subject_template_name="accounts/emails/password_reset_subject.txt",
             success_url="/accounts/password-reset/done/",
         ), name="password_reset"),
    path("password-reset/done/",
         auth_views.PasswordResetDoneView.as_view(
             template_name="accounts/password_reset_done.html"
         ), name="password_reset_done"),
    path("reset/<uidb64>/<token>/",
         auth_views.PasswordResetConfirmView.as_view(
             template_name="accounts/password_reset_confirm.html",
             success_url="/accounts/reset/complete/",
         ), name="password_reset_confirm"),
    path("reset/complete/",
         auth_views.PasswordResetCompleteView.as_view(
             template_name="accounts/password_reset_complete.html"
         ), name="password_reset_complete"),
]