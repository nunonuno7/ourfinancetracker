import pandas as pd
import pytest
from io import BytesIO
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from core.utils import import_helpers
from core.models import Account, DatePeriod, Transaction, AccountBalance
from decimal import Decimal


@pytest.mark.django_db
def test_bulk_importer_valid_creates_accounts_and_periods():
    user = User.objects.create_user('u')
    df = pd.DataFrame({
        'Date': ['2024-01-01', '2024-01-02'],
        'Type': ['IN', 'EX'],
        'Amount': [10, 20],
        'Category': ['Salary', 'Food'],
        'Account': ['Bank', 'Bank'],
    })
    importer = import_helpers.BulkTransactionImporter(user)
    result = importer.import_dataframe(df)
    assert result['imported'] == 2
    assert Account.objects.filter(user=user, name='Bank').exists()
    assert DatePeriod.objects.filter(year=2024, month=1).exists()


@pytest.mark.django_db
def test_bulk_importer_missing_columns():
    user = User.objects.create_user('u2')
    df = pd.DataFrame({'Date': ['2024-01-01'], 'Type': ['IN'], 'Amount': [5], 'Account': ['A']})
    importer = import_helpers.BulkTransactionImporter(user)
    result = importer.import_dataframe(df)
    assert result['errors']


@pytest.mark.django_db
def test_bulk_importer_duplicate_rows():
    user = User.objects.create_user('u3')
    df = pd.DataFrame({
        'Date': ['2024-01-01', '2024-01-01'],
        'Type': ['IN', 'IN'],
        'Amount': [10, 10],
        'Category': ['Salary', 'Salary'],
        'Account': ['Bank', 'Bank'],
    })
    importer = import_helpers.BulkTransactionImporter(user)
    result = importer.import_dataframe(df)
    assert result['imported'] == 2


@pytest.mark.django_db
def test_bulk_importer_large_file_chunked():
    user = User.objects.create_user('u4')
    rows = 2100
    df = pd.DataFrame({
        'Date': ['2024-01-01'] * rows,
        'Type': ['IN'] * rows,
        'Amount': [1] * rows,
        'Category': ['Salary'] * rows,
        'Account': ['Bank'] * rows,
    })
    importer = import_helpers.BulkTransactionImporter(user, batch_size=1000)
    result = importer.import_dataframe(df)
    assert result['imported'] == rows
    assert Transaction.objects.filter(user=user).count() == rows


@pytest.mark.django_db
def test_account_balance_import_and_template(client):
    user = User.objects.create_user('u5', password='x')
    client.force_login(user)
    df = pd.DataFrame({
        'Year': [2024],
        'Month': [1],
        'Account': ['Cash'],
        'Balance': [100.0],
    })
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    file = SimpleUploadedFile('balances.xlsx', output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    client.post(reverse('account_balance_import_xlsx'), {'file': file}, follow=True)
    assert AccountBalance.objects.filter(account__user=user, reported_balance=Decimal('100')).exists()
    response = client.get(reverse('account_balance_template_xlsx'))
    wb = pd.read_excel(BytesIO(response.content))
    assert 'Savings' in wb['Account'].tolist()

@pytest.mark.django_db
def test_account_balance_import_missing_columns(client):
    user = User.objects.create_user('u6', password='x')
    client.force_login(user)
    df = pd.DataFrame({'Year': [2024], 'Month': [1], 'Account': ['Cash']})
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    file = SimpleUploadedFile('balances.xlsx', output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response = client.post(reverse('account_balance_import_xlsx'), {'file': file}, follow=True)
    from django.contrib.messages import get_messages
    messages = [m.message for m in get_messages(response.wsgi_request)]
    assert any('Missing required columns' in m for m in messages)
