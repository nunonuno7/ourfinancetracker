import pytest
from django.urls import reverse
from django.contrib.auth.models import User


@pytest.mark.django_db
def test_delete_account_view(client, settings):
    settings.SECURE_SSL_REDIRECT = False
    user = User.objects.create_user(username="tester", password="secret")
    client.force_login(user)
    response = client.post(reverse("accounts:delete_account"), {
        "password": "secret",
        "confirmation": "DELETE",
    })
    assert response.status_code == 200
    assert not User.objects.filter(username="tester").exists()
