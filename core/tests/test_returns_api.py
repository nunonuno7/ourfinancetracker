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


@pytest.mark.django_db
def test_dashboard_returns_api_computes_monthly_return():
    user = User.objects.create_user(username="u", password="p")
    client = Client()
    client.force_login(user)

    period1 = DatePeriod.objects.create(year=2024, month=1, label="Jan 2024")
    period2 = DatePeriod.objects.create(year=2024, month=2, label="Feb 2024")

    inv_type = AccountType.objects.create(name="Investments")
    currency = get_default_currency()
    account = Account.objects.create(
        user=user,
        name="Broker",
        account_type=inv_type,
        currency=currency,
    )

    AccountBalance.objects.create(
        account=account, period=period1, reported_balance=Decimal("10000")
    )
    AccountBalance.objects.create(
        account=account, period=period2, reported_balance=Decimal("11200")
    )

    Transaction.objects.create(
        user=user,
        amount=Decimal("500"),
        type="IV",
        period=period2,
        account=account,
        date=date(2024, 2, 1),
    )

    url = reverse("dashboard_returns_json") + "?start_period=2024-01&end_period=2024-02"
    response = client.get(url, secure=True)
    assert response.status_code == 200

    data = json.loads(response.content)
    assert "series" in data
    assert len(data["series"]) == 2

    feb_data = data["series"][1]
    expected_return = (
        (Decimal("11200") - (Decimal("10000") + Decimal("500")))
        / (Decimal("10000") + Decimal("500"))
        * Decimal("100")
    )
    assert feb_data["period"] == "2024-02"
    assert feb_data["portfolio_return"] == pytest.approx(float(expected_return), rel=1e-3)
    assert feb_data["avg_portfolio_return"] == pytest.approx(
        float(expected_return), rel=1e-3
    )
