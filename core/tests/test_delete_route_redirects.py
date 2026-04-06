from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from core.models import Account, Category, RecurringTransaction


@pytest.mark.django_db
def test_category_delete_get_redirects_back_to_list(client, django_user_model):
    user = django_user_model.objects.create_user(username="category-delete-user", password="p")
    category = Category.objects.create(user=user, name="Food")

    client.force_login(user)

    response = client.get(reverse("category_delete", args=[category.pk]))

    assert response.status_code == 302
    assert response.url == reverse("category_list")
    assert Category.objects.filter(pk=category.pk).exists()


@pytest.mark.django_db
def test_account_delete_get_redirects_back_to_list(client, django_user_model):
    user = django_user_model.objects.create_user(username="account-delete-user", password="p")
    account = Account.objects.create(user=user, name="Savings 1")

    client.force_login(user)

    response = client.get(reverse("account_delete", args=[account.pk]))

    assert response.status_code == 302
    assert response.url == reverse("account_list")
    assert Account.objects.filter(pk=account.pk).exists()


@pytest.mark.django_db
def test_recurring_delete_get_redirects_back_to_list(client, django_user_model):
    user = django_user_model.objects.create_user(username="recurring-delete-user", password="p")
    recurring = RecurringTransaction.objects.create(
        user=user,
        schedule=RecurringTransaction.Schedule.MONTHLY,
        amount="25.00",
        next_run_at=timezone.now() + timedelta(days=30),
    )

    client.force_login(user)

    response = client.get(reverse("recurring_delete", args=[recurring.pk]))

    assert response.status_code == 302
    assert response.url == reverse("recurring_list")
    assert RecurringTransaction.objects.filter(pk=recurring.pk).exists()
