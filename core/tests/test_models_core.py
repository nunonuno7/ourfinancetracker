import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from core.models import (
    Account, AccountType, Category, Tag, Transaction, DatePeriod, UserSettings
)
from decimal import Decimal
from datetime import date
from django.db import transaction


@pytest.mark.django_db
def test_account_crud_and_unique():
    user = User.objects.create_user('u1')
    acc = Account.objects.create(user=user, name='Main')
    assert acc.currency is not None
    acc.name = 'Main Updated'
    acc.save()
    assert Account.objects.get(pk=acc.pk).name == 'Main Updated'
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Account.objects.create(user=user, name='Main Updated')
    acc.delete()
    assert Account.objects.filter(pk=acc.pk).count() == 0


@pytest.mark.django_db
def test_category_crud_and_unique():
    user = User.objects.create_user('u2')
    cat = Category.objects.create(user=user, name='Food')
    cat.name = 'Food & Drink'
    cat.save()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Category.objects.create(user=user, name='Food & Drink')
    cat.delete()
    assert Category.objects.filter(pk=cat.pk).count() == 0


@pytest.mark.django_db
def test_tag_crud_and_unique():
    user = User.objects.create_user('u3')
    tag = Tag.objects.create(user=user, name='tag1')
    tag.name = 'tag2'
    tag.save()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Tag.objects.create(user=user, name='tag2')
    tag.delete()
    assert Tag.objects.filter(pk=tag.pk).count() == 0


@pytest.mark.django_db
def test_dateperiod_crud_and_validation():
    period = DatePeriod.objects.create(year=2024, month=5, label='May 2024')
    assert period.get_last_day().day in {30, 31}
    period.label = 'May-2024'
    period.save()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DatePeriod.objects.create(year=2024, month=5, label='dup')
    with pytest.raises(ValidationError):
        DatePeriod(year=2024, month=13, label='bad').full_clean()
    period.delete()
    assert DatePeriod.objects.filter(pk=period.pk).count() == 0


@pytest.mark.django_db
def test_transaction_crud_and_validation():
    user = User.objects.create_user('u4')
    category = Category.objects.create(user=user, name='General')
    tx = Transaction.objects.create(user=user, date=date(2024,1,10), amount=Decimal('10'), category=category, type=Transaction.Type.EXPENSE)
    assert tx.period.year == 2024 and tx.period.month == 1
    tx.amount = Decimal('20')
    tx.save()
    with pytest.raises(ValueError):
        t2 = Transaction(user=user, amount=Decimal('5'), type=Transaction.Type.EXPENSE)
        t2.save()
    tx.delete()
    assert Transaction.objects.filter(pk=tx.pk).count() == 0


@pytest.mark.django_db
def test_usersettings_crud():
    user = User.objects.create_user('u5')
    settings = user.settings
    settings.timezone = 'Europe/Lisbon'
    settings.save()
    settings.delete()
    assert UserSettings.objects.filter(user=user).count() == 0


@pytest.mark.django_db
def test_user_creation_creates_settings_and_cash_account():
    user = User.objects.create_user('u6')
    assert hasattr(user, 'settings')
    assert Account.objects.filter(user=user, name__iexact='cash').exists()
