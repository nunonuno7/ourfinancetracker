from decimal import Decimal

import pytest
from django.urls import reverse

from core.models import Account, AccountBalance, DatePeriod


@pytest.mark.django_db
def test_copy_previous_balances_requires_post(client, django_user_model):
    user = django_user_model.objects.create_user(username="copy-post-user", password="p")
    client.force_login(user)

    response = client.get(reverse("copy_previous_balances"))

    assert response.status_code == 200
    assert response.json() == {
        "success": False,
        "error": "POST method required",
    }


@pytest.mark.django_db
def test_copy_previous_balances_returns_error_when_source_period_is_empty(
    client, django_user_model
):
    user = django_user_model.objects.create_user(
        username="copy-empty-source-user",
        password="p",
    )
    client.force_login(user)

    response = client.post(f"{reverse('copy_previous_balances')}?year=2025&month=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"] == "No balances found for 2025-01"


@pytest.mark.django_db
def test_copy_previous_balances_copies_previous_month_for_current_user(
    client, django_user_model
):
    user = django_user_model.objects.create_user(username="copy-balances-user", password="p")
    client.force_login(user)

    prev_period = DatePeriod.objects.create(year=2025, month=1, label="January 2025")
    account = Account.objects.create(user=user, name="Main Savings")
    AccountBalance.objects.create(
        account=account,
        period=prev_period,
        reported_balance=Decimal("1234.56"),
    )

    response = client.post(f"{reverse('copy_previous_balances')}?year=2025&month=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["created"] == 1
    assert payload["updated"] == 0
    assert payload["total"] == 1

    copied_balance = AccountBalance.objects.get(
        account=account,
        period__year=2025,
        period__month=2,
    )
    assert copied_balance.reported_balance == Decimal("1234.56")
