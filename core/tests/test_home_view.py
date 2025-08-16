import pytest
from django.urls import reverse
from django.contrib.auth.models import User


@pytest.mark.django_db
def test_home_view_renders_for_anonymous(client, settings):
    settings.SECURE_SSL_REDIRECT = False
    response = client.get(reverse("home"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_home_view_redirects_authenticated_user(client, settings):
    settings.SECURE_SSL_REDIRECT = False
    user = User.objects.create_user(username="tester", password="secret")
    client.force_login(user)
    response = client.get(reverse("home"))
    assert response.status_code == 302
    assert response.url == reverse("dashboard")
