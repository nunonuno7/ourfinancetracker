# bandit:skip
import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from core.forms import AccountForm
from core.models import Account, AccountType, get_default_currency


@pytest.mark.django_db
def test_account_form_limits_account_type_choices():
    """Account form should only offer Investments and Savings types."""
    user = User.objects.create_user(username="u")
    AccountType.objects.get_or_create(name="Savings")[0]
    AccountType.objects.get_or_create(name="Investments")[0]
    AccountType.objects.get_or_create(name="Checking")[0]

    form = AccountForm(user=user)
    names = list(
        form.fields["account_type"].queryset.values_list("name", flat=True)
    )  # noqa: E501
    assert names == ["Investments", "Savings"]


@pytest.mark.django_db
def test_account_model_rejects_disallowed_account_type():
    """Account.clean should prevent using disallowed account types."""
    user = User.objects.create_user(username="user2")
    invalid_type = AccountType.objects.get_or_create(name="Checking")[0]
    currency = get_default_currency()

    account = Account(
        user=user, name="acc", account_type=invalid_type, currency=currency
    )
    with pytest.raises(ValidationError):
        account.full_clean()


@pytest.mark.django_db
def test_account_form_detects_case_insensitive_duplicates():
    user = User.objects.create_user(username="u3")
    currency = get_default_currency()
    acc_type = AccountType.objects.get_or_create(name="Savings")[0]
    Account.objects.create(
        user=user, name="Main", account_type=acc_type, currency=currency
    )

    data = {
        "name": "main",
        "account_type": acc_type.id,
        "currency": currency.id,
    }

    form = AccountForm(data=data, user=user)
    assert not form.is_valid()
    assert "__all__" in form.errors
