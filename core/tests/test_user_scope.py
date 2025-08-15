import json
from decimal import Decimal
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.test import Client

from core.models import Transaction


@pytest.mark.django_db
@pytest.mark.parametrize("acting_user,expected_status", [
    ("owner", 200),
    ("other", 403),
])
def test_delete_estimated_transaction_scoped(acting_user, expected_status):
    owner = User.objects.create_user(username="owner", password="p")
    other = User.objects.create_user(username="other", password="p")
    tx = Transaction.objects.create(
        user=owner,
        amount=Decimal("1"),
        type=Transaction.Type.EXPENSE,
        date=date.today(),
        is_estimated=True,
    )

    client = Client()
    if acting_user == "owner":
        client.force_login(owner)
    else:
        client.force_login(other)

    url = reverse("delete_estimated_transaction", args=[tx.id])
    response = client.post(url)
    assert response.status_code == expected_status
    if expected_status == 200:
        data = json.loads(response.content)
        assert data["success"] is True
