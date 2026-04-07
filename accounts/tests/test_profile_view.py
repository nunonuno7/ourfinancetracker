import pytest
from django.urls import reverse
from django.contrib.auth.models import User


@pytest.mark.django_db
def test_profile_requires_login(client, settings):
    settings.SECURE_SSL_REDIRECT = False
    response = client.get(reverse("accounts:profile"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_profile_renders_for_authenticated_user(client, settings):
    settings.SECURE_SSL_REDIRECT = False
    user = User.objects.create_user(username="tester", password="secret")
    client.force_login(user)
    response = client.get(reverse("accounts:profile"))
    assert response.status_code == 200
    assert "accounts/profile.html" in [t.name for t in response.templates]
    assert "Username: tester" in response.content.decode()
