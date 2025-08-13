import json
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.urls import reverse

from core.models import (
    Account,
    AccountBalance,
    DatePeriod,
    Transaction,
)
from core.services.finance_estimation import FinanceEstimationService
from core.views import get_estimation_summaries


@pytest.mark.django_db
def test_estimate_created_for_missing_period():
    user = User.objects.create_user(username="u1", password="p")
    account = Account.objects.create(user=user, name="Checking")

    period1 = DatePeriod.objects.create(year=2024, month=1, label="January 2024")
    period2 = DatePeriod.objects.create(year=2024, month=2, label="February 2024")

    AccountBalance.objects.create(account=account, period=period1, reported_balance=Decimal("1000"))
    AccountBalance.objects.create(account=account, period=period2, reported_balance=Decimal("1000"))

    Transaction.objects.create(
        user=user,
        amount=Decimal("1000"),
        type="IN",
        date=date(2024, 1, 1),
        period=period1,
        account=account,
    )

    service = FinanceEstimationService(user)
    est_tx = service.estimate_transaction_for_period(period1)
    assert est_tx is not None
    assert est_tx.is_estimated is True
    assert est_tx.type == "EX"
    assert est_tx.amount == Decimal("1000")


@pytest.mark.django_db(transaction=True)
def test_manual_transaction_deletes_estimate():
    user = User.objects.create_user(username="u2", password="p")
    account = Account.objects.create(user=user, name="Checking")

    period1 = DatePeriod.objects.create(year=2024, month=1, label="January 2024")
    period2 = DatePeriod.objects.create(year=2024, month=2, label="February 2024")

    AccountBalance.objects.create(account=account, period=period1, reported_balance=Decimal("1000"))
    AccountBalance.objects.create(account=account, period=period2, reported_balance=Decimal("1000"))

    Transaction.objects.create(
        user=user,
        amount=Decimal("1000"),
        type="IN",
        date=date(2024, 1, 1),
        period=period1,
        account=account,
    )

    service = FinanceEstimationService(user)
    service.estimate_transaction_for_period(period1)
    assert Transaction.objects.filter(user=user, period=period1, is_estimated=True).count() == 1

    Transaction.objects.create(
        user=user,
        amount=Decimal("1000"),
        type="EX",
        date=date(2024, 1, 5),
        period=period1,
        account=account,
    )

    assert Transaction.objects.filter(user=user, period=period1, is_estimated=True).count() == 0
    assert service.estimate_transaction_for_period(period1) is None


@pytest.mark.django_db(transaction=True)
def test_estimation_summaries_excludes_balanced_period():
    user = User.objects.create_user(username="u3", password="p")
    account = Account.objects.create(user=user, name="Checking")

    period1 = DatePeriod.objects.create(year=2024, month=1, label="January 2024")
    period2 = DatePeriod.objects.create(year=2024, month=2, label="February 2024")

    AccountBalance.objects.create(account=account, period=period1, reported_balance=Decimal("1000"))
    AccountBalance.objects.create(account=account, period=period2, reported_balance=Decimal("1000"))

    Transaction.objects.create(
        user=user,
        amount=Decimal("1000"),
        type="IN",
        date=date(2024, 1, 1),
        period=period1,
        account=account,
    )

    service = FinanceEstimationService(user)
    service.estimate_transaction_for_period(period1)
    Transaction.objects.create(
        user=user,
        amount=Decimal("1000"),
        type="EX",
        date=date(2024, 1, 5),
        period=period1,
        account=account,
    )

    url = reverse("get_estimation_summaries")
    factory = RequestFactory()
    request = factory.get(url)
    request.user = user
    response = get_estimation_summaries(request)
    assert response.status_code == 200
    data = json.loads(response.content)
    period_labels = [s['period'] for s in data['summaries']]
    assert 'January 2024' not in period_labels
