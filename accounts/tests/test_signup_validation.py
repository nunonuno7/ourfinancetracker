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
    assert any("Invalid data" in str(m) for m in messages)
    assert all("username" not in str(m) for m in messages)


@pytest.mark.django_db
def test_signup_invalid_email(client):
    data = {"username": "user", "email": "not-an-email", "password": "StrongPass123!"}
    response = client.post(reverse("accounts:signup"), data)
    assert response.status_code == 400
    assert User.objects.count() == 0
    messages = list(response.context["messages"])
    assert any("Invalid data" in str(m) for m in messages)
    assert all("email" not in str(m) for m in messages)


@pytest.mark.django_db
def test_signup_duplicate_username(client):
    User.objects.create_user(username="existing", email="exist@example.com", password="StrongPass123!")
    data = {"username": "existing", "email": "new@example.com", "password": "StrongPass123!"}
    response = client.post(reverse("accounts:signup"), data)
    assert response.status_code == 400
    assert User.objects.filter(username="existing").count() == 1
    messages = list(response.context["messages"])
    assert any("Invalid data" in str(m) for m in messages)
    assert all("username" not in str(m) for m in messages)


@pytest.mark.django_db
def test_signup_duplicate_email(client):
    User.objects.create_user(username="user1", email="dup@example.com", password="StrongPass123!")
    data = {"username": "user2", "email": "dup@example.com", "password": "StrongPass123!"}
    response = client.post(reverse("accounts:signup"), data)
    assert response.status_code == 400
    assert User.objects.filter(email="dup@example.com").count() == 1
    messages = list(response.context["messages"])
    assert any("Invalid data" in str(m) for m in messages)
    assert all("email" not in str(m) for m in messages)
