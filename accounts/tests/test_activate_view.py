import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from accounts.tokens import generate_activation_token


@pytest.mark.django_db
def test_activate_view_with_valid_token(client, settings):
    settings.SECURE_SSL_REDIRECT = False
    user = User.objects.create_user(
        username="newuser", email="new@example.com", password="pass", is_active=False
    )
    token = generate_activation_token(user)
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

    response = client.get(reverse("accounts:activate", kwargs={"uidb64": uidb64, "token": token}))
    user.refresh_from_db()
    assert response.status_code == 200
    assert user.is_active


@pytest.mark.django_db
def test_activate_view_with_invalid_token(client, settings):
    settings.SECURE_SSL_REDIRECT = False
    user = User.objects.create_user(
        username="newuser", email="new@example.com", password="pass", is_active=False
    )
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

    response = client.get(reverse("accounts:activate", kwargs={"uidb64": uidb64, "token": "bad"}))
    user.refresh_from_db()
    assert response.status_code == 400
    assert not user.is_active
