import pytest
from django.urls import reverse
from django.contrib.auth.models import User


@pytest.mark.django_db
def test_signup_missing_username(client):
    data = {"email": "test@example.com", "password": "StrongPass123!"}
    response = client.post(reverse("accounts:signup"), data)
    assert response.status_code == 400
    assert User.objects.count() == 0
    messages = [str(m) for m in response.context["messages"]]
    assert any("Username" in m and "required" in m for m in messages)


@pytest.mark.django_db
def test_signup_invalid_email(client):
    data = {"username": "user", "email": "not-an-email", "password": "StrongPass123!"}
    response = client.post(reverse("accounts:signup"), data)
    assert response.status_code == 400
    assert User.objects.count() == 0
    messages = [str(m) for m in response.context["messages"]]
    assert any("Email" in m and "valid" in m for m in messages)


@pytest.mark.django_db
def test_signup_duplicate_username(client):
    User.objects.create_user(username="existing", email="exist@example.com", password="StrongPass123!")
    data = {"username": "existing", "email": "new@example.com", "password": "StrongPass123!"}
    response = client.post(reverse("accounts:signup"), data)
    assert response.status_code == 400
    assert User.objects.filter(username="existing").count() == 1
    messages = [str(m) for m in response.context["messages"]]
    assert any("Username already taken" in m for m in messages)


@pytest.mark.django_db
def test_signup_duplicate_email(client):
    User.objects.create_user(username="user1", email="dup@example.com", password="StrongPass123!")
    data = {"username": "user2", "email": "dup@example.com", "password": "StrongPass123!"}
    response = client.post(reverse("accounts:signup"), data)
    assert response.status_code == 400
    assert User.objects.filter(email="dup@example.com").count() == 1
    messages = [str(m) for m in response.context["messages"]]
    assert any("Email already registered" in m for m in messages)


@pytest.mark.django_db
def test_signup_reuse_inactive_username(client):
    User.objects.create_user(
        username="inactive", email="old@example.com", password="StrongPass123!", is_active=False
    )
    data = {"username": "inactive", "email": "new@example.com", "password": "StrongPass123!"}
    response = client.post(reverse("accounts:signup"), data)
    assert response.status_code == 200
    assert User.objects.filter(username="inactive", email="new@example.com").count() == 1


@pytest.mark.django_db
def test_signup_reuse_inactive_email(client):
    User.objects.create_user(
        username="olduser", email="reusable@example.com", password="StrongPass123!", is_active=False
    )
    data = {"username": "newuser", "email": "reusable@example.com", "password": "StrongPass123!"}
    response = client.post(reverse("accounts:signup"), data)
    assert response.status_code == 200
    assert User.objects.filter(username="newuser", email="reusable@example.com").count() == 1
