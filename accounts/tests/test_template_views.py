import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.mark.django_db
def test_login_page_renders(client):
    response = client.get(reverse("accounts:login"))
    assert response.status_code == 200
    assert "accounts/login.html" in [t.name for t in response.templates]


@pytest.mark.django_db
def test_login_invalid_credentials_render_clean_non_field_error(client):
    user_model = get_user_model()
    user_model.objects.create_user(username="tester", password="secret")

    response = client.post(
        reverse("accounts:login"),
        {"username": "tester", "password": "wrong"},
    )

    assert response.status_code == 200
    assert b"Please enter a correct username and password" in response.content
    assert b"__all__" not in response.content


@pytest.mark.django_db
def test_signup_page_renders(client):
    response = client.get(reverse("accounts:signup"))
    assert response.status_code == 200
    assert "accounts/signup.html" in [t.name for t in response.templates]


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", [
    "accounts:password_reset",
    "accounts:password_reset_done",
    "accounts:password_reset_complete",
])
def test_password_reset_pages_render(client, url_name):
    response = client.get(reverse(url_name))
    assert response.status_code == 200


@pytest.mark.django_db
def test_delete_account_page_requires_login(client, django_user_model):
    user = django_user_model.objects.create_user(username="u", password="p")
    client.force_login(user)
    response = client.get(reverse("accounts:delete_account"))
    assert response.status_code == 200
