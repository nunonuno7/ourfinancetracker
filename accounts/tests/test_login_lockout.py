import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.cache import cache


@pytest.mark.django_db
def test_login_lockout_after_failures(client, settings):
    settings.SECURE_SSL_REDIRECT = False
    cache.clear()
    User.objects.create_user(username="tester", password="secret")
    url = reverse("accounts:login")
    for _ in range(5):
        client.post(url, {"username": "tester", "password": "wrong"})
    response = client.post(url, {"username": "tester", "password": "wrong"})
    assert response.status_code == 200
    messages = list(response.context["messages"])
    assert any("Account locked" in str(m) for m in messages)


@pytest.mark.django_db
def test_login_success_resets_failed_attempts(client, settings):
    settings.SECURE_SSL_REDIRECT = False
    cache.clear()
    User.objects.create_user(username="tester", password="secret")
    url = reverse("accounts:login")
    for _ in range(4):
        client.post(url, {"username": "tester", "password": "wrong"})
    assert cache.get("failed_tester") == 4
    response = client.post(url, {"username": "tester", "password": "secret"})
    assert response.status_code == 302
    assert cache.get("failed_tester") is None
