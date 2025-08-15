from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest
from django.core.management import call_command
from django.contrib.auth.models import User

from core.models import (
    Account,
    AccountType,
    Currency,
    DatePeriod,
    FxRate,
    Transaction,
    UserSettings,
    convert_amount,
    get_default_currency,
)
from core.views import build_kpis_for_period


@pytest.mark.django_db
def test_fetch_ecb_rates_creates_rates(monkeypatch):
    data = {"date": "2024-01-01", "rates": {"USD": 1.2, "GBP": 0.9, "EUR": 1}}

    def fake_get(url, params=None):
        resp = Mock()
        resp.json.return_value = data
        resp.raise_for_status = Mock()
        return resp

    monkeypatch.setattr("requests.get", fake_get)

    call_command("fetch_ecb_rates")
    assert FxRate.objects.filter(date=date(2024, 1, 1)).count() == 2


@pytest.mark.django_db
def test_convert_amount_uses_rate():
    eur = get_default_currency()
    usd, _ = Currency.objects.get_or_create(code="USD")
    FxRate.objects.create(date=date(2024, 1, 1), base=eur, quote=usd, rate=Decimal("2.0"))
    result = convert_amount(Decimal("10"), usd, eur, date(2024, 1, 1))
    assert result == Decimal("5.00")


@pytest.mark.django_db
def test_kpi_cache_invalidated_on_fx_rate_change():
    user = User.objects.create_user(username="u", password="p")
    eur = get_default_currency()
    usd, _ = Currency.objects.get_or_create(code="USD")
    settings = user.settings
    settings.base_currency = eur
    settings.default_currency = eur
    settings.save()

    acc_type, _ = AccountType.objects.get_or_create(name="Investments")
    account = Account.objects.create(user=user, name="Broker", account_type=acc_type, currency=usd)
    period = DatePeriod.objects.create(year=2024, month=1, label="Jan 2024")
    Transaction.objects.create(
        user=user,
        amount=Decimal("10"),
        type="IN",
        account=account,
        date=date(2024, 1, 1),
        period=period,
    )

    rate = FxRate.objects.create(date=date(2024, 1, 1), base=eur, quote=usd, rate=Decimal("2.0"))
    first = build_kpis_for_period(user, "2024-01")
    assert first["income"] == 5.0

    rate.rate = Decimal("4.0")
    rate.save()
    second = build_kpis_for_period(user, "2024-01")
    assert second["income"] == 2.5
