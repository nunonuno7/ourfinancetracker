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
             email_template_name="accounts/emails/password_reset_email.html",  # Use our custom template
             subject_template_name="accounts/emails/password_reset_subject.txt",
             extra_email_context={
                 "domain": getattr(settings, 'EMAIL_LINK_DOMAIN', 'localhost:5000'),
                 "site_name": "OurFinanceTracker",
                 "protocol": "https",
                 "expiry_human": f"{settings.PASSWORD_RESET_TIMEOUT // 60} hour(s)" # Added expiry_human
             },
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