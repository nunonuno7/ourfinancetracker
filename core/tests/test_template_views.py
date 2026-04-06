import pytest
from django.db import connection
from django.urls import reverse

from core.models import Tag


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


@pytest.mark.django_db
def test_transaction_create_context_includes_only_users_tags(client, django_user_model):
    user = django_user_model.objects.create_user(username="tags-user", password="p")
    other_user = django_user_model.objects.create_user(username="other-tags-user", password="p")
    Tag.objects.create(user=user, name="groceries")
    Tag.objects.create(user=user, name="monthly")
    Tag.objects.create(user=other_user, name="private-tag")

    client.force_login(user)
    response = client.get(reverse("transaction_create"))

    assert response.status_code == 200
    assert set(response.context["tag_list"]) == {"groceries", "monthly"}
