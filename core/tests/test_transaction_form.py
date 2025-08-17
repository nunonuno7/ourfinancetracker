import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from core.forms import TransactionForm
from core.models import Transaction, Category
from django.core.exceptions import ValidationError


@pytest.mark.django_db
def test_clean_amount_handles_thousand_and_comma():
    user = User.objects.create_user('u', password='x')
    form = TransactionForm(user=user)
    form.data = {'amount': '1.234,56'}
    assert form.clean_amount() == Decimal('1234.56')


@pytest.mark.django_db
def test_clean_amount_comma_decimal():
    user = User.objects.create_user('u2')
    form = TransactionForm(user=user)
    form.data = {'amount': '10,50'}
    assert form.clean_amount() == Decimal('10.50')


@pytest.mark.django_db
def test_negative_amount_not_allowed_for_expense():
    user = User.objects.create_user('u3')
    data = {
        'date': '2024-01-10',
        'type': Transaction.Type.EXPENSE,
        'amount': '-5',
        'period': '2024-01',
        'category': 'Food',
    }
    form = TransactionForm(data=data, user=user)
    assert not form.is_valid()
    assert 'amount' in form.errors


@pytest.mark.django_db
def test_direction_applies_sign_for_investment():
    user = User.objects.create_user('u4')
    data = {
        'date': '2024-01-10',
        'type': Transaction.Type.INVESTMENT,
        'amount': '100',
        'direction': 'OUT',
        'period': '2024-01',
        'category': 'Invest',
    }
    form = TransactionForm(data=data, user=user)
    assert form.is_valid(), form.errors
    tx = form.save()
    assert tx.amount == Decimal('-100')


@pytest.mark.django_db
def test_invalid_and_valid_period():
    user = User.objects.create_user('u5')
    data = {
        'date': '2024-01-10',
        'type': Transaction.Type.EXPENSE,
        'amount': '10',
        'period': 'bad-format',
        'category': 'Food',
    }
    form = TransactionForm(data=data, user=user)
    assert form.is_valid()
    with pytest.raises(ValueError):
        form.save()
    data['period'] = '2024-12'
    form = TransactionForm(data=data, user=user)
    assert form.is_valid()
    tx = form.save()
    assert tx.period.month == 12


@pytest.mark.django_db
def test_tags_saved_and_loaded():
    user = User.objects.create_user('u6')
    data = {
        'date': '2024-01-10',
        'type': Transaction.Type.EXPENSE,
        'amount': '10',
        'period': '2024-01',
        'category': 'Food',
        'tags_input': 'foo, bar',
    }
    form = TransactionForm(data=data, user=user)
    assert form.is_valid(), form.errors
    tx = form.save()
    assert set(tx.tags.values_list('name', flat=True)) == {'foo', 'bar'}
    edit_form = TransactionForm(user=user, instance=tx)
    assert set(edit_form.initial['tags_input'].split(', ')) == {'foo', 'bar'}
