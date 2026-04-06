from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.models import Account, Category, DatePeriod, Tag, Transaction
from core.views import transactions_json_v2, transactions_totals_v2


def _cash_account_for(user):
    return Account.objects.get(user=user, name="Cash")


def _make_transaction(
    *, user, account, category, amount, tx_type, tx_date, period=None
):
    return Transaction.objects.create(
        user=user,
        account=account,
        category=category,
        amount=Decimal(amount),
        type=tx_type,
        date=tx_date,
        period=period,
    )


@pytest.mark.django_db
def test_transactions_json_v2_paginates_sorted_results(client, django_user_model):
    user = django_user_model.objects.create_user(username="json-v2-page", password="p")
    client.force_login(user)

    cash = _cash_account_for(user)
    category = Category.objects.create(user=user, name="General")

    _make_transaction(
        user=user,
        account=cash,
        category=category,
        amount="10.00",
        tx_type=Transaction.Type.EXPENSE,
        tx_date=date(2024, 1, 5),
    )
    tx_mid = _make_transaction(
        user=user,
        account=cash,
        category=category,
        amount="20.00",
        tx_type=Transaction.Type.EXPENSE,
        tx_date=date(2024, 1, 6),
    )
    _make_transaction(
        user=user,
        account=cash,
        category=category,
        amount="30.00",
        tx_type=Transaction.Type.EXPENSE,
        tx_date=date(2024, 1, 7),
    )

    response = client.get(
        reverse("transactions_json_v2"),
        {
            "date_start": "2024-01-01",
            "date_end": "2024-12-31",
            "page": 2,
            "page_size": 1,
            "sort_field": "amount",
            "sort_direction": "asc",
            "include_system": "true",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["total_count"] == 3
    assert payload["current_page"] == 2
    assert payload["page_size"] == 1
    assert [tx["id"] for tx in payload["transactions"]] == [tx_mid.id]
    assert payload["transactions"][0]["amount"] == float(tx_mid.amount)
    assert payload["filters"]["categories"] == [
        {"value": category.id, "label": "General"}
    ]


@pytest.mark.django_db
def test_transactions_json_v2_filter_options_follow_other_active_filters(
    client, django_user_model
):
    user = django_user_model.objects.create_user(
        username="json-v2-filters", password="p"
    )
    client.force_login(user)

    cash = _cash_account_for(user)
    second_account = Account.objects.create(
        user=user,
        name="Savings Pot",
        account_type=cash.account_type,
        currency=cash.currency,
    )

    groceries = Category.objects.create(user=user, name="Groceries")
    rent = Category.objects.create(user=user, name="Rent")
    feb_2024 = DatePeriod.objects.create(year=2024, month=2, label="2024-02")

    wallet_expense = _make_transaction(
        user=user,
        account=cash,
        category=groceries,
        amount="45.00",
        tx_type=Transaction.Type.EXPENSE,
        tx_date=date(2024, 2, 1),
        period=feb_2024,
    )
    _make_transaction(
        user=user,
        account=second_account,
        category=rent,
        amount="800.00",
        tx_type=Transaction.Type.EXPENSE,
        tx_date=date(2024, 2, 2),
        period=feb_2024,
    )
    _make_transaction(
        user=user,
        account=cash,
        category=groceries,
        amount="2500.00",
        tx_type=Transaction.Type.INCOME,
        tx_date=date(2024, 2, 3),
        period=feb_2024,
    )

    response = client.get(
        reverse("transactions_json_v2"),
        {
            "date_start": "2024-01-01",
            "date_end": "2024-12-31",
            "type": Transaction.Type.EXPENSE,
            "account_id": cash.id,
            "include_system": "true",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert [tx["id"] for tx in payload["transactions"]] == [wallet_expense.id]
    assert payload["transactions"][0]["account_id"] == cash.id
    assert payload["transactions"][0]["category_id"] == groceries.id
    assert payload["filters"]["types"] == [
        {"value": Transaction.Type.EXPENSE, "label": "Expense"},
        {"value": Transaction.Type.INCOME, "label": "Income"},
    ]
    assert payload["filters"]["categories"] == [
        {"value": groceries.id, "label": "Groceries"}
    ]
    assert payload["filters"]["accounts"] == [
        {"value": cash.id, "label": "Cash"},
        {"value": second_account.id, "label": "Savings Pot"},
    ]
    assert payload["filters"]["periods"] == [
        {"value": "2024-02", "label": "2024-02"}
    ]


@pytest.mark.django_db
def test_transactions_json_v2_keeps_legacy_name_filters_compatible(
    client, django_user_model
):
    user = django_user_model.objects.create_user(
        username="json-v2-legacy-filters", password="p"
    )
    client.force_login(user)

    cash = _cash_account_for(user)
    groceries = Category.objects.create(user=user, name="Groceries")
    Category.objects.create(user=user, name="Rent")

    matching_expense = _make_transaction(
        user=user,
        account=cash,
        category=groceries,
        amount="45.00",
        tx_type=Transaction.Type.EXPENSE,
        tx_date=date(2024, 2, 1),
    )
    _make_transaction(
        user=user,
        account=cash,
        category=groceries,
        amount="2500.00",
        tx_type=Transaction.Type.INCOME,
        tx_date=date(2024, 2, 3),
    )

    response = client.get(
        reverse("transactions_json_v2"),
        {
            "date_start": "2024-01-01",
            "date_end": "2024-12-31",
            "type": Transaction.Type.EXPENSE,
            "account": "Cash",
            "category": "Grocer",
            "include_system": "true",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [tx["id"] for tx in payload["transactions"]] == [matching_expense.id]


@pytest.mark.django_db
def test_transactions_json_v2_search_matches_type_display_label(
    client, django_user_model
):
    user = django_user_model.objects.create_user(
        username="json-v2-search", password="p"
    )
    client.force_login(user)

    cash = _cash_account_for(user)
    category = Category.objects.create(user=user, name="Brokerage")

    investment = _make_transaction(
        user=user,
        account=cash,
        category=category,
        amount="100.00",
        tx_type=Transaction.Type.INVESTMENT,
        tx_date=date(2024, 3, 10),
    )
    _make_transaction(
        user=user,
        account=cash,
        category=category,
        amount="15.00",
        tx_type=Transaction.Type.EXPENSE,
        tx_date=date(2024, 3, 11),
    )

    response = client.get(
        reverse("transactions_json_v2"),
        {
            "date_start": "2024-01-01",
            "date_end": "2024-12-31",
            "search": "invest",
            "include_system": "true",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [tx["id"] for tx in payload["transactions"]] == [investment.id]


@patch(
    "core.views_transactions.get_transaction_list_default_date_range",
    return_value=(date(2024, 1, 1), date(2026, 4, 6)),
)
@pytest.mark.django_db
def test_transactions_json_v2_uses_shared_default_range_when_dates_omitted(
    _mocked_range,
    client,
    django_user_model,
):
    user = django_user_model.objects.create_user(
        username="json-v2-default-range", password="p"
    )
    client.force_login(user)

    cash = _cash_account_for(user)
    category = Category.objects.create(user=user, name="General")

    old_tx = _make_transaction(
        user=user,
        account=cash,
        category=category,
        amount="10.00",
        tx_type=Transaction.Type.EXPENSE,
        tx_date=date(2023, 12, 31),
    )
    in_range_tx = _make_transaction(
        user=user,
        account=cash,
        category=category,
        amount="20.00",
        tx_type=Transaction.Type.EXPENSE,
        tx_date=date(2024, 1, 1),
    )

    response = client.get(
        reverse("transactions_json_v2"),
        {"include_system": "true"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] == 1
    assert [tx["id"] for tx in payload["transactions"]] == [in_range_tx.id]
    assert old_tx.id not in [tx["id"] for tx in payload["transactions"]]


@pytest.mark.django_db
def test_transactions_totals_v2_respects_tag_filters_without_double_counting(
    client, django_user_model
):
    user = django_user_model.objects.create_user(
        username="json-v2-totals", password="p"
    )
    client.force_login(user)

    cash = _cash_account_for(user)
    category = Category.objects.create(user=user, name="Food")
    groceries = Tag.objects.create(user=user, name="groceries")
    monthly = Tag.objects.create(user=user, name="monthly")

    tagged_expense = _make_transaction(
        user=user,
        account=cash,
        category=category,
        amount="30.00",
        tx_type=Transaction.Type.EXPENSE,
        tx_date=date(2024, 4, 1),
    )
    tagged_expense.tags.add(groceries, monthly)

    other_expense = _make_transaction(
        user=user,
        account=cash,
        category=category,
        amount="20.00",
        tx_type=Transaction.Type.EXPENSE,
        tx_date=date(2024, 4, 2),
    )
    other_expense.tags.add(monthly)

    response = client.post(
        reverse("transactions_totals_v2"),
        data='{"date_start":"2024-01-01","date_end":"2024-12-31","tags":"groc","include_system":true}',
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["income"] == 0.0
    assert payload["expenses"] == 30.0
    assert payload["balance"] == -30.0


@pytest.mark.django_db
def test_transactions_json_v2_reuses_filter_options_cache_across_sort_changes(
    rf, django_user_model
):
    cache.clear()
    user = django_user_model.objects.create_user(
        username="json-v2-filter-cache", password="p"
    )
    cash = _cash_account_for(user)
    category = Category.objects.create(user=user, name="General")

    _make_transaction(
        user=user,
        account=cash,
        category=category,
        amount="10.00",
        tx_type=Transaction.Type.EXPENSE,
        tx_date=date(2024, 5, 1),
    )
    _make_transaction(
        user=user,
        account=cash,
        category=category,
        amount="20.00",
        tx_type=Transaction.Type.EXPENSE,
        tx_date=date(2024, 5, 2),
    )

    warm_request = rf.get(
        reverse("transactions_json_v2"),
        {
            "date_start": "2024-01-01",
            "date_end": "2024-12-31",
            "page": 1,
            "page_size": 1,
            "sort_field": "date",
            "sort_direction": "desc",
            "include_system": "true",
        },
    )
    warm_request.user = user
    warm_response = transactions_json_v2(warm_request)

    assert warm_response.status_code == 200

    second_request = rf.get(
        reverse("transactions_json_v2"),
        {
            "date_start": "2024-01-01",
            "date_end": "2024-12-31",
            "page": 2,
            "page_size": 1,
            "sort_field": "amount",
            "sort_direction": "asc",
            "include_system": "true",
        },
    )
    second_request.user = user

    with CaptureQueriesContext(connection) as captured:
        second_response = transactions_json_v2(second_request)

    assert second_response.status_code == 200
    assert len(captured) == 3


@pytest.mark.django_db
def test_transactions_totals_v2_cache_ignores_page_and_sort_state(
    rf, django_user_model
):
    cache.clear()
    user = django_user_model.objects.create_user(
        username="json-v2-totals-cache", password="p"
    )
    cash = _cash_account_for(user)
    category = Category.objects.create(user=user, name="General")

    _make_transaction(
        user=user,
        account=cash,
        category=category,
        amount="100.00",
        tx_type=Transaction.Type.INCOME,
        tx_date=date(2024, 6, 1),
    )

    warm_request = rf.post(
        reverse("transactions_totals_v2"),
        data='{"date_start":"2024-01-01","date_end":"2024-12-31","page":1,"page_size":25,"sort_field":"date","sort_direction":"desc","include_system":true}',
        content_type="application/json",
    )
    warm_request.user = user
    warm_response = transactions_totals_v2(warm_request)

    assert warm_response.status_code == 200

    second_request = rf.post(
        reverse("transactions_totals_v2"),
        data='{"date_start":"2024-01-01","date_end":"2024-12-31","page":3,"page_size":10,"sort_field":"amount","sort_direction":"asc","include_system":true}',
        content_type="application/json",
    )
    second_request.user = user

    with CaptureQueriesContext(connection) as captured:
        second_response = transactions_totals_v2(second_request)

    assert second_response.status_code == 200
    assert len(captured) == 0
