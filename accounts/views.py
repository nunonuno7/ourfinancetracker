import logging
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.core.mail import send_mail
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.views import PasswordResetView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.db import transaction, IntegrityError
from django.contrib import messages
from django.conf import settings
from .tokens import account_activation_token

logger = logging.getLogger(__name__)

def signup(request):
    if request.method == "POST":
        username = request.POST["username"].strip()
        email = request.POST["email"].strip().lower()
        password = request.POST["password"]

        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, "This username is already taken. Please choose another one.")
            return render(request, "accounts/signup.html", status=400)

        # Se já existir conta ativa com este email
        if User.objects.filter(email__iexact=email, is_active=True).exists():
            messages.error(request, "An account with this email already exists. Try resetting your password.")
            return render(request, "accounts/signup.html", status=400)

        # Se existir conta inativa com o mesmo email, reenvia ativação em vez de criar nova
        existing_inactive = User.objects.filter(email__iexact=email, is_active=False).first()
        if existing_inactive:
            # Generate activation token for existing user
            token = account_activation_token.make_token(existing_inactive)
            uid = urlsafe_base64_encode(force_bytes(existing_inactive.pk))

            # Send activation email
            activation_link = request.build_absolute_uri(
                reverse('accounts:activate', kwargs={'uidb64': uid, 'token': token})
            )

            try:
                message = render_to_string(
                    'accounts/emails/account_activation_email.txt',
                    {
                        'user': existing_inactive,
                        'activation_link': activation_link,
                    },
                )
                html_message = render_to_string(
                    'accounts/emails/account_activation_email.html',
                    {
                        'user': existing_inactive,
                        'activation_link': activation_link,
                    },
                )
                send_mail(
                    'Activate your account',
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [existing_inactive.email],
                    html_message=html_message,
                )
            except Exception as e:
                # Em desenvolvimento, apenas mostra o link de ativação no console
                if settings.DEBUG:
                    logger.exception("📧 Email sending failed in development: %s", e)
                    logger.warning("🔗 Activation link: %s", activation_link)
                else:
                    raise

            messages.info(request, "We have resent the activation link to your email.")
            return render(request, "accounts/check_email.html")

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username, email=email, password=password, is_active=False
                )
        except IntegrityError:
            messages.error(request, "This username is already taken. Please choose another one.")
            return render(request, "accounts/signup.html", status=400)

        # Generate activation token
        token = account_activation_token.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Send activation email
        activation_link = request.build_absolute_uri(
            reverse('accounts:activate', kwargs={'uidb64': uid, 'token': token})
        )

        try:
            message = render_to_string(
                'accounts/emails/account_activation_email.txt',
                {
                    'user': user,
                    'activation_link': activation_link,
                },
            )
            html_message = render_to_string(
                'accounts/emails/account_activation_email.html',
                {
                    'user': user,
                    'activation_link': activation_link,
                },
            )
            send_mail(
                'Activate your account',
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=html_message,
            )
        except Exception as e:
            # Em desenvolvimento, apenas mostra o link de ativação no console
            if settings.DEBUG:
                logger.exception("📧 Email sending failed in development: %s", e)
                logger.warning("🔗 Activation link: %s", activation_link)
            else:
                raise

        return render(request, "accounts/check_email.html")

    return render(request, "accounts/signup.html")

def activate(request, uidb64, token):
    """
    Activate an account from the emailed link.

    Behavior:
    - Decodes uidb64 -> user id
    - Verifies the token
    - Marks user as active if needed
    - Logs the user in with an explicit backend to avoid ValueError
    - Renders success or invalid templates instead of 500
    """
    user = None
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except Exception as exc:
        logger.warning("Activation: could not resolve user from uidb64=%s (%s)", uidb64, exc)

    if user and account_activation_token.check_token(user, token):
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
        # IMPORTANT: specify backend or Django will raise ValueError
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return render(request, "accounts/activation_success.html", status=200)

    logger.info("Activation failed for uidb64=%s", uidb64)
    return render(request, "accounts/activation_invalid.html", status=400)


class OFTPasswordResetView(PasswordResetView):
    """Custom password reset view with consistent styling and domain override."""
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/emails/password_reset_email.txt'
    html_email_template_name = 'accounts/emails/password_reset_email.html'
    subject_template_name = 'accounts/emails/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')

    def get_form(self, form_class=None):
        """Override to ensure consistent domain and protocol"""
        form = super().get_form(form_class)
        # Store these on the form so they're used when form.save() is called
        form.domain_override = 'www.ourfinancetracker.com'
        form.use_https = True
        return form


from django.contrib.auth.decorators import login_required


@login_required
def profile(request):
    return render(request, "accounts/profile.html")


class DeleteAccountView(View):
    """Handle account deletion and show a success page."""

    def get(self, request):
        """Render a confirmation/success page even on direct access."""
        return render(request, "accounts/account_deleted.html")

    def post(self, request):
        if not request.user.is_authenticated:
            login_url = f"{reverse('accounts:login')}?next={reverse('accounts:delete_account')}"
            return redirect(login_url)

        password = request.POST.get("password", "")
        confirmation = request.POST.get("confirmation", "")
        user = request.user

        if confirmation != "DELETE" or not authenticate(username=user.username, password=password):
            referer = request.META.get("HTTP_REFERER") or reverse("home")
            separator = "&" if "?" in referer else "?"
            return redirect(f"{referer}{separator}delete_error=1")

        with transaction.atomic():
            user.delete()
            logout(request)

        return render(request, "accounts/account_deleted.html")
