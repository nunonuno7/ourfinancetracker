from datetime import date
from decimal import Decimal

import pytest
from django.db import connection

from core.models import Account, Category, DatePeriod, Tag, Transaction


def _period_expr() -> str:
    if connection.vendor == "sqlite":
        return "CAST(p.year AS TEXT) || '-' || printf('%02d', p.month)"
    return "CONCAT(p.year, '-', LPAD(p.month::text, 2, '0'))"


def _tag_agg_expr() -> str:
    if connection.vendor == "sqlite":
        return "GROUP_CONCAT(tag.name, ', ')"
    return "STRING_AGG(tag.name, ', ')"


@pytest.mark.django_db
def test_sql_query_filters_by_user_and_returns_joined_data(django_user_model):
    user = django_user_model.objects.create_user(username="sql-user", password="secret")
    other_user = django_user_model.objects.create_user(
        username="other-sql-user", password="secret"
    )
    period = DatePeriod.objects.create(year=2025, month=3, label="March 2025")
    category = Category.objects.create(user=user, name="Food")
    other_category = Category.objects.create(user=other_user, name="Travel")
    account = Account.objects.create(user=user, name="Main")
    other_account = Account.objects.create(user=other_user, name="Backup")
    tag = Tag.objects.create(user=user, name="Urgent")

    transaction = Transaction.objects.create(
        user=user,
        date=date(2025, 3, 15),
        type=Transaction.Type.EXPENSE,
        amount=Decimal("12.34"),
        category=category,
        account=account,
        period=period,
    )
    transaction.tags.add(tag)

    Transaction.objects.create(
        user=other_user,
        date=date(2025, 3, 16),
        type=Transaction.Type.EXPENSE,
        amount=Decimal("99.99"),
        category=other_category,
        account=other_account,
        period=period,
    )

    query = f"""
        SELECT
          t.date,
          t.type,
          t.amount,
          COALESCE(c.name, '') AS category,
          COALESCE({_tag_agg_expr()}, '') AS tags,
          COALESCE(a.name, '') AS account,
          {_period_expr()} AS period
        FROM core_transaction t
        LEFT JOIN core_category c ON t.category_id = c.id
        LEFT JOIN core_account a ON t.account_id = a.id
        LEFT JOIN core_dateperiod p ON t.period_id = p.id
        LEFT JOIN core_transactiontag tt ON t.id = tt.transaction_id
        LEFT JOIN core_tag tag ON tag.id = tt.tag_id
        WHERE t.user_id = %s
        GROUP BY t.id, t.date, t.type, t.amount, c.name, a.name, p.year, p.month
        ORDER BY t.date DESC
    """

    with connection.cursor() as cursor:
        cursor.execute(query, [user.id])
        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

    assert len(rows) == 1

    row = rows[0]
    assert row["date"] == date(2025, 3, 15)
    assert row["type"] == Transaction.Type.EXPENSE
    assert Decimal(str(row["amount"])) == Decimal("12.34")
    assert row["category"] == "Food"
    assert row["tags"] == "Urgent"
    assert row["account"] == "Main"
    assert row["period"] == "2025-03"
