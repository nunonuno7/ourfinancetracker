import pandas as pd
import pytest
from io import BytesIO
from datetime import date
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from core.utils import import_helpers
from core.models import (
    Account,
    AccountBalance,
    AccountType,
    Category,
    DatePeriod,
    Transaction,
    get_default_currency,
)
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
def test_bulk_importer_allows_empty_account_values():
    user = User.objects.create_user('u_empty_account')
    existing_account_names = set(Account.objects.filter(user=user).values_list('name', flat=True))
    df = pd.DataFrame({
        'Date': ['2024-01-01', '2024-01-02'],
        'Type': ['IN', 'EX'],
        'Amount': [10, 20],
        'Category': ['Salary', 'Food'],
        'Account': ['', None],
    })
    importer = import_helpers.BulkTransactionImporter(user)
    result = importer.import_dataframe(df)
    assert result['imported'] == 2
    transactions = Transaction.objects.filter(user=user).order_by('date')
    assert transactions.count() == 2
    assert all(transaction.account is None for transaction in transactions)
    assert set(Account.objects.filter(user=user).values_list('name', flat=True)) == existing_account_names
    assert not Account.objects.filter(user=user, name='').exists()


@pytest.mark.django_db
def test_bulk_importer_account_column_is_optional():
    user = User.objects.create_user('u_optional_account_col')
    df = pd.DataFrame({
        'Date': ['2024-01-01'],
        'Type': ['IN'],
        'Amount': [10],
        'Category': ['Salary'],
    })
    importer = import_helpers.BulkTransactionImporter(user)
    result = importer.import_dataframe(df)
    assert result['imported'] == 1
    transaction = Transaction.objects.get(user=user)
    assert transaction.account is None


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
def test_bulk_importer_amount_with_comma_decimal():
    user = User.objects.create_user('u_comma')
    df = pd.DataFrame({
        'Date': ['2024-01-01'],
        'Type': ['IN'],
        'Amount': ['10,35'],
        'Category': ['Salary'],
        'Account': ['Bank'],
    })
    importer = import_helpers.BulkTransactionImporter(user)
    result = importer.import_dataframe(df)
    assert result['imported'] == 1
    transaction = Transaction.objects.get(user=user)
    assert transaction.amount == Decimal('10.35')


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


@pytest.mark.django_db
def test_data_export_without_filters_includes_all_transactions_and_balances(client):
    user = User.objects.create_user('export_user', password='x')
    client.force_login(user)

    currency = get_default_currency()
    account_type = AccountType.objects.get_or_create(name='Savings')[0]
    account = Account.objects.create(
        user=user,
        name='Main Account',
        account_type=account_type,
        currency=currency,
    )
    category = Category.objects.create(user=user, name='Salary')
    period = DatePeriod.objects.create(year=2024, month=3, label='Mar 2024')

    Transaction.objects.create(
        user=user,
        date=date(2024, 3, 15),
        period=period,
        type=Transaction.Type.INCOME,
        amount=Decimal('123.45'),
        category=category,
        account=account,
        notes='Monthly salary',
    )
    AccountBalance.objects.create(
        account=account,
        period=period,
        reported_balance=Decimal('999.99'),
    )

    response = client.get(reverse('data_export_xlsx'))

    assert response.status_code == 200
    assert response['Content-Disposition'] == 'attachment; filename="data_export_all.xlsx"'

    workbook = pd.ExcelFile(BytesIO(response.content))
    transactions = pd.read_excel(workbook, sheet_name='Transactions')
    balances = pd.read_excel(workbook, sheet_name='Account_Balances')

    assert transactions['Category'].tolist() == ['Salary']
    assert transactions['Account'].tolist() == ['Main Account']
    assert transactions['Notes'].tolist() == ['Monthly salary']
    assert str(transactions.loc[0, 'Date'].date()) == '2024-03-15'
    assert transactions.loc[0, 'Amount'] == pytest.approx(123.45)

    expected_balance = balances[
        (balances['Period'] == '2024-03')
        & (balances['Account_Name'] == 'Main Account')
    ]
    assert len(expected_balance) == 1
    assert expected_balance.iloc[0]['Balance'] == pytest.approx(999.99)


@pytest.mark.django_db
def test_data_export_with_filters_limits_transactions_only(client):
    user = User.objects.create_user('filtered_export_user', password='x')
    client.force_login(user)

    currency = get_default_currency()
    account_type = AccountType.objects.get_or_create(name='Savings')[0]
    account = Account.objects.create(
        user=user,
        name='Savings',
        account_type=account_type,
        currency=currency,
    )
    category = Category.objects.create(user=user, name='Food')
    jan = DatePeriod.objects.create(year=2024, month=1, label='Jan 2024')
    feb = DatePeriod.objects.create(year=2024, month=2, label='Feb 2024')

    Transaction.objects.create(
        user=user,
        date=date(2024, 1, 10),
        period=jan,
        type=Transaction.Type.EXPENSE,
        amount=Decimal('10.00'),
        category=category,
        account=account,
    )
    Transaction.objects.create(
        user=user,
        date=date(2024, 2, 20),
        period=feb,
        type=Transaction.Type.EXPENSE,
        amount=Decimal('20.00'),
        category=category,
        account=account,
    )
    AccountBalance.objects.create(
        account=account,
        period=feb,
        reported_balance=Decimal('250.00'),
    )

    response = client.get(
        reverse('data_export_xlsx'),
        {'date_start': '2024-02-01', 'date_end': '2024-02-29'},
    )

    assert response.status_code == 200
    assert (
        response['Content-Disposition']
        == 'attachment; filename="data_export_2024-02-01_2024-02-29.xlsx"'
    )

    workbook = pd.ExcelFile(BytesIO(response.content))
    transactions = pd.read_excel(workbook, sheet_name='Transactions')
    balances = pd.read_excel(workbook, sheet_name='Account_Balances')

    assert transactions['Amount'].tolist() == [20]
    assert str(transactions.loc[0, 'Date'].date()) == '2024-02-20'
    filtered_balance = balances[
        (balances['Period'] == '2024-02')
        & (balances['Account_Name'] == 'Savings')
    ]
    assert len(filtered_balance) == 1
    assert filtered_balance.iloc[0]['Balance'] == pytest.approx(250.00)
