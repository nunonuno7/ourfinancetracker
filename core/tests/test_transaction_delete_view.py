from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from core.models import Transaction


@pytest.mark.django_db
def test_transaction_delete_ajax_returns_json_and_removes_transaction(
    client, django_user_model
):
    user = django_user_model.objects.create_user(username="delete-user", password="p")
    transaction = Transaction.objects.create(
        user=user,
        date=date(2024, 1, 10),
        amount=Decimal("12.34"),
        type=Transaction.Type.EXPENSE,
    )

    client.force_login(user)

    response = client.post(
        reverse("transaction_delete", args=[transaction.pk]),
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Transaction deleted successfully!",
    }
    assert not Transaction.objects.filter(pk=transaction.pk).exists()


@pytest.mark.django_db
def test_transaction_delete_get_redirects_back_to_list(
    client, django_user_model
):
    user = django_user_model.objects.create_user(username="delete-get-user", password="p")
    transaction = Transaction.objects.create(
        user=user,
        date=date(2024, 1, 10),
        amount=Decimal("12.34"),
        type=Transaction.Type.EXPENSE,
    )

    client.force_login(user)

    response = client.get(reverse("transaction_delete", args=[transaction.pk]))

    assert response.status_code == 302
    assert response.url == reverse("transaction_list_v2")
    assert Transaction.objects.filter(pk=transaction.pk).exists()


@pytest.mark.django_db
def test_transaction_delete_does_not_allow_deleting_other_users_transaction(
    client, django_user_model
):
    owner = django_user_model.objects.create_user(username="owner", password="p")
    other_user = django_user_model.objects.create_user(username="other", password="p")
    transaction = Transaction.objects.create(
        user=owner,
        date=date(2024, 1, 10),
        amount=Decimal("20.00"),
        type=Transaction.Type.EXPENSE,
    )

    client.force_login(other_user)

    response = client.post(
        reverse("transaction_delete", args=[transaction.pk]),
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 404
    assert Transaction.objects.filter(pk=transaction.pk).exists()
