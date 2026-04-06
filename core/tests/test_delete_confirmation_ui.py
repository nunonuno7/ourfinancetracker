from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from core.models import Account, Category, RecurringTransaction


@pytest.mark.django_db
def test_account_list_renders_delete_confirmation_attributes(client, django_user_model):
    user = django_user_model.objects.create_user(username="account-user", password="p")
    Account.objects.create(user=user, name="Brokerage")

    client.force_login(user)
    response = client.get(reverse("account_list"))

    assert response.status_code == 200
    html = response.content.decode()
    assert 'data-confirm-method="post"' in html
    assert "Delete this account? This action cannot be undone." in html


@pytest.mark.django_db
def test_category_list_renders_delete_confirmation_attributes(client, django_user_model):
    user = django_user_model.objects.create_user(username="category-user", password="p")
    Category.objects.create(user=user, name="Food")

    client.force_login(user)
    response = client.get(reverse("category_list"))

    assert response.status_code == 200
    html = response.content.decode()
    assert 'data-confirm-method="post"' in html
    assert "Delete this category? This action cannot be undone." in html


@pytest.mark.django_db
def test_recurring_list_renders_delete_confirmation_attributes(client, django_user_model):
    user = django_user_model.objects.create_user(username="recurring-user", password="p")
    RecurringTransaction.objects.create(
        user=user,
        schedule=RecurringTransaction.Schedule.MONTHLY,
        amount="25.00",
        next_run_at=timezone.now() + timedelta(days=30),
    )

    client.force_login(user)
    response = client.get(reverse("recurring_list"))

    assert response.status_code == 200
    html = response.content.decode()
    assert 'data-confirm-method="post"' in html
    assert "Delete this recurring transaction? This action cannot be undone." in html
