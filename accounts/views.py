from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.shortcuts import render, redirect
from django.urls import reverse
from django.core.mail import send_mail
from django.contrib.auth import login
from django.db import transaction, IntegrityError
from django.contrib import messages
from django.conf import settings
from .tokens import account_activation_token

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
                send_mail(
                    'Activate your account',
                    render_to_string('accounts/emails/account_activation_email.txt', {
                        'user': existing_inactive,
                        'activation_link': activation_link,
                    }),
                    settings.DEFAULT_FROM_EMAIL,
                    [existing_inactive.email],
                )
            except Exception as e:
                # Em desenvolvimento, apenas mostra o link de ativação no console
                if settings.DEBUG:
                    print(f"📧 Email sending failed in development: {e}")
                    print(f"🔗 Activation link: {activation_link}")
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
            send_mail(
                'Activate your account',
                render_to_string('accounts/emails/account_activation_email.txt', {
                    'user': user,
                    'activation_link': activation_link,
                }),
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
            )
        except Exception as e:
            # Em desenvolvimento, apenas mostra o link de ativação no console
            if settings.DEBUG:
                print(f"📧 Email sending failed in development: {e}")
                print(f"🔗 Activation link: {activation_link}")
            else:
                raise

        return render(request, "accounts/check_email.html")

    return render(request, "accounts/signup.html")

def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except Exception:
        user = None
    if user and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        return render(request, "accounts/activation_success.html")
    return render(request, "accounts/activation_invalid.html", status=400)