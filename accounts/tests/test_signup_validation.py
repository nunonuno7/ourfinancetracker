import pytest
from django.urls import reverse
from django.contrib.auth.models import User


@pytest.mark.django_db
def test_signup_missing_username(client):
    data = {"email": "test@example.com", "password": "StrongPass123!"}
    response = client.post(reverse("accounts:signup"), data)
    assert response.status_code == 400
    assert User.objects.count() == 0
    messages = list(response.context["messages"])
    assert any("username" in str(m) for m in messages)


@pytest.mark.django_db
def test_signup_invalid_email(client):
    data = {"username": "user", "email": "not-an-email", "password": "StrongPass123!"}
    response = client.post(reverse("accounts:signup"), data)
    assert response.status_code == 400
    assert User.objects.count() == 0
    messages = list(response.context["messages"])
    assert any("email" in str(m) for m in messages)
