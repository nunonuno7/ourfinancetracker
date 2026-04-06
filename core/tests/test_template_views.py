from datetime import date
from unittest.mock import patch

import pytest
from django.db import connection
from django.urls import reverse

from core.models import Tag, Transaction


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


@pytest.mark.django_db
def test_transaction_list_v2_bootstraps_initial_filters_from_query_string(
    client, django_user_model
):
    user = django_user_model.objects.create_user(username="list-filters-user", password="p")
    client.force_login(user)

    response = client.get(
        reverse("transaction_list_v2"),
        {
            "category": "Groceries",
            "period": "2025-01",
            "date_start": "2025-01-01",
            "date_end": "2025-01-31",
            "type": Transaction.Type.EXPENSE,
        },
    )

    assert response.status_code == 200
    html = response.content.decode()
    assert f'action="{reverse("transaction_list_v2")}"' in html
    assert 'id="transaction-list-initial-filters"' in html
    assert '"category": "Groceries"' in html
    assert '"period": "2025-01"' in html
    assert '"date_start": "2025-01-01"' in html
    assert '"date_end": "2025-01-31"' in html
    assert f'"type": "{Transaction.Type.EXPENSE}"' in html


@patch(
    "core.views_transactions.get_transaction_list_default_date_range",
    return_value=(date(2024, 1, 1), date(2026, 4, 6)),
)
@pytest.mark.django_db
def test_transaction_list_v2_uses_shared_default_date_range(
    _mocked_range,
    client,
    django_user_model,
):
    user = django_user_model.objects.create_user(username="list-defaults-user", password="p")
    client.force_login(user)

    response = client.get(reverse("transaction_list_v2"))

    assert response.status_code == 200
    assert response.context["default_date_start"] == "2024-01-01"
    assert response.context["default_date_end"] == "2026-04-06"
    html = response.content.decode()
    assert 'value="2024-01-01"' in html
    assert 'value="2026-04-06"' in html
    assert 'id="transaction-list-defaults"' in html
    assert '"date_start": "2024-01-01"' in html
    assert '"date_end": "2026-04-06"' in html
