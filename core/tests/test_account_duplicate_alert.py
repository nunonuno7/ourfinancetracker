import pytest
from django.urls import reverse

from core.models import Account, AccountType, get_default_currency


@pytest.mark.django_db
def test_duplicate_account_creation_shows_error(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="u", password="p"
    )  # nosec B106
    client.force_login(user)

    currency = get_default_currency()
    acc_type = AccountType.objects.get_or_create(name="Savings")[0]
    Account.objects.create(
        user=user, name="Main", account_type=acc_type, currency=currency
    )

    data = {
        "name": "main",  # duplicate differing only by case
        "account_type": acc_type.id,
        "currency": currency.id,
    }

    response = client.post(reverse("account_create"), data)
    assert response.status_code == 200  # nosec B101
    message = b"An account with this name already exists"
    assert message in response.content  # nosec B101
