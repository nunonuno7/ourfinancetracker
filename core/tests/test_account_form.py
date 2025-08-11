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
    names = list(form.fields["account_type"].queryset.values_list("name", flat=True))
    assert names == ["Investments", "Savings"]


@pytest.mark.django_db
def test_account_model_rejects_disallowed_account_type():
    """Account.clean should prevent using disallowed account types."""
    user = User.objects.create_user(username="user2")
    invalid_type = AccountType.objects.get_or_create(name="Checking")[0]
    currency = get_default_currency()

    account = Account(user=user, name="acc", account_type=invalid_type, currency=currency)
    with pytest.raises(ValidationError):
        account.full_clean()
