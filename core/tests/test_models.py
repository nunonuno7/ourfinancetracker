import pytest
from core.tests.factories import TransactionFactory, CategoryFactory

@pytest.mark.django_db
def test_category_unique_per_user():
    cat1 = CategoryFactory(name="Utilities")
    with pytest.raises(Exception):
        CategoryFactory(user=cat1.user, name="Utilities")

@pytest.mark.django_db
def test_transaction_negative_amount_for_expense():
    tx = TransactionFactory(type="expense", amount=50)
    assert tx.amount < 0  # regra implementada no modelo?
