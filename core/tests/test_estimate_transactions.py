import json
from decimal import Decimal
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db import connection

from core.models import (
    AccountType,
    Account,
    Category,
    DatePeriod,
    AccountBalance,
    Transaction,
)
from core.services.finance_estimation import FinanceEstimationService
from core.utils.cache_helpers import clear_tx_cache


@pytest.fixture
def user(client):
    User = get_user_model()
    user = User.objects.create_user(username="tester", password="pass")
    client.force_login(user)
    return user


@pytest.fixture
def savings_account(user):
    savings_type, _ = AccountType.objects.get_or_create(name="Savings")
    return Account.objects.create(user=user, name="Main", account_type=savings_type)


@pytest.fixture
def category(user):
    return Category.objects.create(user=user, name="General")


def make_period(label: str) -> DatePeriod:
    year, month = map(int, label.split("-"))
    period, _ = DatePeriod.objects.get_or_create(
        year=year, month=month, defaults={"label": label}
    )
    if period.label != label:
        period.label = label
        period.save()
    return period


def set_balance(account: Account, period: DatePeriod, amount: Decimal) -> None:
    balance, _ = AccountBalance.objects.get_or_create(
        account=account,
        period=period,
        defaults={"reported_balance": Decimal(str(amount))},
    )
    if balance.reported_balance != Decimal(str(amount)):
        balance.reported_balance = Decimal(str(amount))
        balance.save(update_fields=["reported_balance"])


def make_tx(
    *, user, account, category, period, amount, tx_type="EX", is_estimated=False
):
    return Transaction.objects.create(
        user=user,
        account=account,
        category=category,
        period=period,
        date=date(period.year, period.month, 1),
        amount=Decimal(str(amount)),
        type=tx_type,
        is_estimated=is_estimated,
    )


def run_estimate_for(client, period: DatePeriod):
    url = reverse("estimate_transaction_for_period")
    resp = client.post(
        url,
        data=json.dumps({"period_id": period.id}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.json()
    if data.get("transaction_id"):
        return Transaction.objects.get(id=data["transaction_id"])
    return None


@pytest.mark.django_db
def test_estimate_creates_single_estimated_transaction_for_period(
    client, user, savings_account
):
    period_aug = make_period("2025-08")
    period_sep = make_period("2025-09")
    set_balance(savings_account, period_aug, Decimal("1000"))
    set_balance(savings_account, period_sep, Decimal("800"))

    tx1 = run_estimate_for(client, period_aug)
    assert tx1 is not None
    assert (
        Transaction.objects.filter(
            user=user, period=period_aug, is_estimated=True
        ).count()
        == 1
    )

    run_estimate_for(client, period_aug)
    assert (
        Transaction.objects.filter(
            user=user, period=period_aug, is_estimated=True
        ).count()
        == 1
    )


@pytest.mark.django_db
@pytest.mark.skipif(
    connection.vendor == "sqlite",
    reason="transactions_json_v2 uses PostgreSQL-specific SQL",
)
def test_estimated_transaction_is_visible_on_transactions_v2_page(
    client, user, savings_account
):
    period_aug = make_period("2025-08")
    period_sep = make_period("2025-09")
    set_balance(savings_account, period_aug, Decimal("1000"))
    set_balance(savings_account, period_sep, Decimal("800"))

    run_estimate_for(client, period_aug)

    url = reverse("transactions_json_v2")
    resp = client.get(
        url,
        {
            "date_start": "2025-08-01",
            "date_end": "2025-08-31",
            "include_system": "true",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["transactions"]
    assert any(tx["is_estimated"] and tx["period"] == "2025-08" for tx in data)


@pytest.mark.django_db
def test_estimate_marks_period_balanced_when_missing_covered(
    client, user, savings_account
):
    period_aug = make_period("2025-08")
    period_sep = make_period("2025-09")
    set_balance(savings_account, period_aug, Decimal("1000"))
    set_balance(savings_account, period_sep, Decimal("800"))

    run_estimate_for(client, period_aug)
    service = FinanceEstimationService(user)
    summary = service.get_estimation_summary(period_aug)
    assert summary["status"] == "balanced"
    assert Decimal(str(summary["details"]["currently_estimating"])) == Decimal("200")


@pytest.mark.django_db
def test_manual_transaction_after_estimate_triggers_reestimate_warning(
    client, user, savings_account, category
):
    period_aug = make_period("2025-08")
    period_sep = make_period("2025-09")
    set_balance(savings_account, period_aug, Decimal("1000"))
    set_balance(savings_account, period_sep, Decimal("800"))

    run_estimate_for(client, period_aug)
    make_tx(
        user=user,
        account=savings_account,
        category=category,
        period=period_aug,
        amount=Decimal("50"),
        tx_type="EX",
    )
    clear_tx_cache(user.id, force=True)

    service = FinanceEstimationService(user)
    summary = service.get_estimation_summary(period_aug)
    assert summary["has_estimated_transaction"] is True
    assert summary["status"] != "balanced"
    assert Decimal(str(summary["estimated_amount"])) == Decimal("150")


@pytest.mark.django_db
@pytest.mark.skipif(
    connection.vendor == "sqlite",
    reason="transactions_json_v2 uses PostgreSQL-specific SQL",
)
def test_reestimate_replaces_previous_estimate_and_keeps_single_per_period(
    client, user, savings_account, category
):
    period_aug = make_period("2025-08")
    period_sep = make_period("2025-09")
    set_balance(savings_account, period_aug, Decimal("1000"))
    set_balance(savings_account, period_sep, Decimal("800"))

    first = run_estimate_for(client, period_aug)
    make_tx(
        user=user,
        account=savings_account,
        category=category,
        period=period_aug,
        amount=Decimal("50"),
        tx_type="EX",
    )
    clear_tx_cache(user.id, force=True)
    second = run_estimate_for(client, period_aug)

    qs = Transaction.objects.filter(user=user, period=period_aug, is_estimated=True)
    assert qs.count() == 1
    assert second.id != first.id

    url = reverse("transactions_json_v2")
    resp = client.get(
        url,
        {
            "date_start": "2025-08-01",
            "date_end": "2025-08-31",
            "include_system": "true",
        },
    )
    data = resp.json()["transactions"]
    assert any(tx["id"] == second.id and tx["is_estimated"] for tx in data)


@pytest.mark.django_db
def test_reestimate_does_not_affect_other_periods(
    client, user, savings_account, category
):
    period_aug = make_period("2025-08")
    period_sep = make_period("2025-09")
    period_oct = make_period("2025-10")
    set_balance(savings_account, period_aug, Decimal("1000"))
    set_balance(savings_account, period_sep, Decimal("800"))
    set_balance(savings_account, period_oct, Decimal("700"))

    aug_tx = run_estimate_for(client, period_aug)
    sep_tx = run_estimate_for(client, period_sep)

    make_tx(
        user=user,
        account=savings_account,
        category=category,
        period=period_aug,
        amount=Decimal("50"),
        tx_type="EX",
    )
    clear_tx_cache(user.id, force=True)
    aug_tx2 = run_estimate_for(client, period_aug)

    qs_aug = Transaction.objects.filter(user=user, period=period_aug, is_estimated=True)
    qs_sep = Transaction.objects.filter(user=user, period=period_sep, is_estimated=True)

    assert qs_aug.count() == 1
    assert qs_aug.first().id == aug_tx2.id
    assert qs_sep.count() == 1
    assert qs_sep.first().id == sep_tx.id
