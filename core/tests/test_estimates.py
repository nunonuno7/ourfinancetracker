import json
from decimal import Decimal

import pytest
from django.test import Client

from core.models import Transaction, DatePeriod, Account


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="u", password="p")


@pytest.fixture
def client_logged(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def period():
    return DatePeriod.objects.create(year=2024, month=1, label="2024-01")


@pytest.fixture
def account(user):
    return Account.objects.create(user=user, name="Main")


def _estimate_params(period, account, tx_type="EX"):
    return {
        "period_id": period.id,
        "type": tx_type,
        "account_id": account.id,
    }


def test_preview_ignores_existing_estimate(client_logged, user, period, account):
    Transaction.objects.create(
        user=user,
        period=period,
        account=account,
        type="EX",
        amount=Decimal("100"),
        date=period.get_last_day(),
    )
    Transaction.objects.create(
        user=user,
        period=period,
        account=account,
        type="EX",
        amount=Decimal("60"),
        date=period.get_last_day(),
        is_estimated=True,
    )
    resp = client_logged.get("/transactions/estimate/", _estimate_params(period, account))
    data = resp.json()
    assert Decimal(str(data["estimated_amount"])) == Decimal("100")
    assert Decimal(str(data["current_estimate"])) == Decimal("60")
    assert data["will_replace"] is True


def test_preview_without_estimate(client_logged, user, period, account):
    Transaction.objects.create(
        user=user,
        period=period,
        account=account,
        type="EX",
        amount=Decimal("40"),
        date=period.get_last_day(),
    )
    resp = client_logged.get("/transactions/estimate/", _estimate_params(period, account))
    data = resp.json()
    assert Decimal(str(data["estimated_amount"])) == Decimal("40")
    assert data["current_estimate"] is None
    assert data["will_replace"] is False


def test_reestimate_replaces_only_one(client_logged, user, period, account):
    Transaction.objects.create(
        user=user,
        period=period,
        account=account,
        type="EX",
        amount=Decimal("80"),
        date=period.get_last_day(),
    )
    Transaction.objects.create(
        user=user,
        period=period,
        account=account,
        type="EX",
        amount=Decimal("50"),
        date=period.get_last_day(),
        is_estimated=True,
    )
    params = _estimate_params(period, account)
    preview = client_logged.get("/transactions/estimate/", params).json()
    assert Decimal(str(preview["estimated_amount"])) == Decimal("80")
    resp = client_logged.post(
        "/transactions/estimate/",
        json.dumps(params),
        content_type="application/json",
    )
    assert resp.status_code == 201
    qs = Transaction.objects.filter(user=user, period=period, type="EX", is_estimated=True)
    assert qs.count() == 1
    assert qs.first().amount == Decimal("80")


def test_preview_after_manual_transaction(client_logged, user, period, account):
    Transaction.objects.create(
        user=user,
        period=period,
        account=account,
        type="EX",
        amount=Decimal("30"),
        date=period.get_last_day(),
    )
    Transaction.objects.create(
        user=user,
        period=period,
        account=account,
        type="EX",
        amount=Decimal("20"),
        date=period.get_last_day(),
        is_estimated=True,
    )
    params = _estimate_params(period, account)
    first = client_logged.get("/transactions/estimate/", params).json()
    assert Decimal(str(first["estimated_amount"])) == Decimal("30")
    # add new actual transaction
    Transaction.objects.create(
        user=user,
        period=period,
        account=account,
        type="EX",
        amount=Decimal("10"),
        date=period.get_last_day(),
    )
    second = client_logged.get("/transactions/estimate/", params).json()
    assert Decimal(str(second["estimated_amount"])) == Decimal("40")


def test_atomic_and_uniqueness(user, period, account):
    Transaction.objects.create(
        user=user,
        period=period,
        account=account,
        type="EX",
        amount=Decimal("25"),
        date=period.get_last_day(),
    )
    data = json.dumps(_estimate_params(period, account))
    c = Client()
    c.force_login(user)
    for _ in range(2):
        c.post("/transactions/estimate/", data, content_type="application/json")
    assert Transaction.objects.filter(user=user, period=period, type="EX", is_estimated=True).count() == 1

