import pytest
from django.urls import reverse
from django.db import connection


@pytest.mark.django_db
@pytest.mark.skipif(connection.vendor == "sqlite", reason="Dashboard view uses PostgreSQL-specific SQL")
def test_dashboard_page_render(client, django_user_model):
    user = django_user_model.objects.create_user(username="u", password="p")
    client.force_login(user)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", [
    "transaction_list_v2",
    "account_list",
    "account_balance",
    "category_list",
    "account_create",
    "transaction_create",
    "category_create",
])
def test_core_html_pages_render_for_authenticated_users(client, django_user_model, url_name):
    user = django_user_model.objects.create_user(username="u", password="p")
    client.force_login(user)
    response = client.get(reverse(url_name))
    assert response.status_code == 200
