from django.utils import timezone
from celery import shared_task

from .models import RecurringTransaction, Transaction


@shared_task
def process_recurring_transactions():
    """Create transactions for due recurring definitions."""
    now = timezone.now()
    qs = RecurringTransaction.objects.filter(active=True, next_run_at__lte=now)
    for rt in qs.select_related("account", "category").prefetch_related("tags"):
        tx, created = Transaction.objects.get_or_create(
            user=rt.user,
            date=rt.next_run_at.date(),
            amount=rt.amount,
            account=rt.account,
            category=rt.category,
            notes=f"Recurring {rt.id}",
            defaults={"type": Transaction.Type.EXPENSE},
        )
        if created and rt.tags.exists():
            tx.tags.set(rt.tags.all())
        rt.schedule_next()
