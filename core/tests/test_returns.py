import json
from decimal import Decimal
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from core.models import (
    Account,
    AccountBalance,
    AccountType,
    DatePeriod,
    Transaction,
    get_default_currency,
)


@pytest.fixture
def investment_env(db):
    """Create a user, account and three periods for return tests."""
    user = User.objects.create_user(username="u", password="p")
    client = Client()
    client.force_login(user)

    inv_type = AccountType.objects.create(name="Investments")
    currency = get_default_currency()
    account = Account.objects.create(
        user=user,
        name="Broker",
        account_type=inv_type,
        currency=currency,
    )

    p1 = DatePeriod.objects.create(year=2024, month=1, label="Jan 2024")
    p2 = DatePeriod.objects.create(year=2024, month=2, label="Feb 2024")
    p3 = DatePeriod.objects.create(year=2024, month=3, label="Mar 2024")
    return user, client, account, (p1, p2, p3)


def _call_api(client, start, end):
    url = reverse("dashboard_returns_json") + f"?start_period={start}&end_period={end}"
    response = client.get(url, secure=True)
    assert response.status_code == 200
    return json.loads(response.content)


@pytest.mark.django_db
def test_portfolio_return_positive(investment_env):
    user, client, account, (p1, p2, _) = investment_env

    AccountBalance.objects.create(account=account, period=p1, reported_balance=Decimal("10000"))
    AccountBalance.objects.create(account=account, period=p2, reported_balance=Decimal("11200"))
    Transaction.objects.create(
        user=user,
        amount=Decimal("500"),
        type="IV",
        period=p2,
        account=account,
        date=date(2024, 2, 1),
    )

    data = _call_api(client, "2024-01", "2024-02")
    feb = data["series"][1]
    expected = (
        (Decimal("11200") - (Decimal("10000") + Decimal("500")))
        / (Decimal("10000") + Decimal("500"))
        * Decimal("100")
    )
    assert feb["portfolio_return"] == pytest.approx(float(expected), rel=1e-3)
    assert feb["avg_portfolio_return"] == pytest.approx(float(expected), rel=1e-3)


@pytest.mark.django_db
def test_zero_denominator_returns_none(investment_env):
    _, client, account, (p1, p2, _) = investment_env

    AccountBalance.objects.create(account=account, period=p1, reported_balance=Decimal("0"))
    AccountBalance.objects.create(account=account, period=p2, reported_balance=Decimal("0"))

    data = _call_api(client, "2024-01", "2024-02")
    assert data["series"][1]["portfolio_return"] is None
    assert data["series"][1]["avg_portfolio_return"] is None


@pytest.mark.django_db
def test_no_investments_returns_expected(investment_env):
    _, client, account, (p1, p2, _) = investment_env

    AccountBalance.objects.create(account=account, period=p1, reported_balance=Decimal("1000"))
    AccountBalance.objects.create(account=account, period=p2, reported_balance=Decimal("1100"))

    data = _call_api(client, "2024-01", "2024-02")
    expected = (Decimal("1100") - Decimal("1000")) / Decimal("1000") * Decimal("100")
    feb = data["series"][1]
    assert feb["portfolio_return"] == pytest.approx(float(expected), rel=1e-3)


@pytest.mark.django_db
def test_negative_period_return(investment_env):
    user, client, account, (p1, p2, _) = investment_env

    AccountBalance.objects.create(account=account, period=p1, reported_balance=Decimal("1000"))
    AccountBalance.objects.create(account=account, period=p2, reported_balance=Decimal("700"))
    Transaction.objects.create(
        user=user,
        amount=Decimal("-200"),
        type="IV",
        period=p2,
        account=account,
        date=date(2024, 2, 1),
    )

    data = _call_api(client, "2024-01", "2024-02")
    expected = (
        (Decimal("700") - (Decimal("1000") + Decimal("-200")))
        / (Decimal("1000") + Decimal("-200"))
        * Decimal("100")
    )
    feb = data["series"][1]
    assert feb["portfolio_return"] == pytest.approx(float(expected), rel=1e-3)
