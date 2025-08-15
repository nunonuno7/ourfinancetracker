import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta

from core.models import Category, Account, RecurringTransaction, Transaction, Tag
from core.tasks import process_recurring_transactions


@pytest.mark.django_db
def test_schedule_next():
    user = User.objects.create_user("u1")
    cat = Category.objects.create(user=user, name="Food")
    acc = Account.objects.create(user=user, name="Wallet")
    now = timezone.now()
    rt_daily = RecurringTransaction.objects.create(user=user, schedule="daily", category=cat, account=acc, amount=1, next_run_at=now)
    rt_weekly = RecurringTransaction.objects.create(user=user, schedule="weekly", category=cat, account=acc, amount=1, next_run_at=now)
    rt_monthly = RecurringTransaction.objects.create(user=user, schedule="monthly", category=cat, account=acc, amount=1, next_run_at=now)
    rt_daily.schedule_next()
    rt_weekly.schedule_next()
    rt_monthly.schedule_next()
    assert rt_daily.next_run_at.date() == (now + timedelta(days=1)).date()
    assert rt_weekly.next_run_at.date() == (now + timedelta(weeks=1)).date()
    assert rt_monthly.next_run_at.date() == (now + relativedelta(months=1)).date()


@pytest.mark.django_db
def test_task_creates_transaction_and_reschedules():
    user = User.objects.create_user("u2")
    cat = Category.objects.create(user=user, name="Bills")
    acc = Account.objects.create(user=user, name="Checking")
    tag = Tag.objects.create(user=user, name="Auto")
    past = timezone.now() - timedelta(days=1)
    rt = RecurringTransaction.objects.create(user=user, schedule="daily", category=cat, account=acc, amount=10, next_run_at=past)
    rt.tags.add(tag)
    process_recurring_transactions()
    tx = Transaction.objects.get(user=user, notes=f"Recurring {rt.id}")
    assert tx.amount == 10
    assert tag in tx.tags.all()
    rt.refresh_from_db()
    assert rt.next_run_at.date() == (past + timedelta(days=1)).date()


@pytest.mark.django_db
def test_task_idempotent():
    user = User.objects.create_user("u3")
    cat = Category.objects.create(user=user, name="Rent")
    acc = Account.objects.create(user=user, name="Bank")
    past = timezone.now() - timedelta(days=1)
    rt = RecurringTransaction.objects.create(user=user, schedule="daily", category=cat, account=acc, amount=20, next_run_at=past)
    process_recurring_transactions()
    # reset to simulate second run for same schedule
    rt.next_run_at = past
    rt.save(update_fields=["next_run_at"])
    process_recurring_transactions()
    count = Transaction.objects.filter(user=user, notes=f"Recurring {rt.id}").count()
    assert count == 1
