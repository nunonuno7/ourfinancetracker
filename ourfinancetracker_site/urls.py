from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views
from django.conf import settings

def signup_redirect(request):
    return redirect('/accounts/signup/')

urlpatterns = [
    path("", include("core.urls")),         # Inclui as views principais
    path("site-admin/", admin.site.urls),  # was "admin/"
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("signup/", signup_redirect, name="signup"),  # Redirect to accounts signup
]

# Django auth password reset URLs - centralized in main URLs
urlpatterns += [
    path("accounts/password-reset/",
         auth_views.PasswordResetView.as_view(
             template_name="accounts/password_reset.html",
             email_template_name="accounts/emails/password_reset_email.txt",
             subject_template_name="accounts/emails/password_reset_subject.txt",
             extra_email_context={
                 "domain": getattr(settings, 'EMAIL_LINK_DOMAIN', 'localhost:5000'),
                 "site_name": "OurFinanceTracker",
                 "protocol": "https",
             },
             success_url="/accounts/password-reset/done/",
         ), name="password_reset"),
    path("accounts/password-reset/done/",
         auth_views.PasswordResetDoneView.as_view(
             template_name="accounts/password_reset_done.html"
         ), name="password_reset_done"),
    path("accounts/reset/<uidb64>/<token>/",
         auth_views.PasswordResetConfirmView.as_view(
             template_name="accounts/password_reset_confirm.html",
             success_url="/accounts/reset/complete/",
         ), name="password_reset_confirm"),
    path("accounts/reset/complete/",
         auth_views.PasswordResetCompleteView.as_view(
             template_name="accounts/password_reset_complete.html"
         ), name="password_reset_complete"),
]

if settings.DEBUG and getattr(settings, "SHOW_DEBUG_TOOLBAR", False):
    import debug_toolbar
    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns