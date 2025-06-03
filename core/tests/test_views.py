import pytest
from decimal import Decimal
from django.urls import reverse
from core.models import Transaction
from core.tests.factories import UserFactory, CategoryFactory, TransactionFactory


@pytest.mark.django_db
def test_create_transaction_view(client):
    user = UserFactory()
    client.force_login(user)
    cat = CategoryFactory(user=user)

    response = client.post(
        reverse("transaction_create"),
        data={
            "amount": "250",
            "date": "2025-06-01",
            "type": "income",
            "category": cat.id,
        },
        follow=True,
    )
    assert response.status_code == 200
    assert user.transaction_set.count() == 1


@pytest.mark.django_db
def test_update_transaction_view(client):
    user = UserFactory()
    txn = TransactionFactory(user=user, amount=100)
    client.force_login(user)

    url = reverse("transaction_update", kwargs={"pk": txn.pk})

    data = {
        "amount": "200",
        "date": txn.date,
        "type": txn.type,
        "category": txn.category_id,
        "is_estimated": False,
        "notes": "updated",
    }

    # 👉 efectua o POST para actualizar
    response = client.post(url, data=data, follow=True)

    txn.refresh_from_db()

    assert response.status_code == 200
    assert txn.amount == Decimal("200")
    assert txn.notes == "updated"


@pytest.mark.django_db
def test_delete_transaction_view(client):
    user = UserFactory()
    txn = TransactionFactory(user=user)
    client.force_login(user)

    url = reverse("transaction_delete", kwargs={"pk": txn.pk})
    response = client.post(url, follow=True)
    assert response.status_code == 200
    assert not Transaction.objects.filter(pk=txn.pk).exists()
