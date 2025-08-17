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


@shared_task
def import_transactions_task(user_id, file_path):
    """Import transactions from an uploaded Excel file."""
    from django.contrib.auth import get_user_model
    import pandas as pd
    from pathlib import Path
    from .utils.import_helpers import BulkTransactionImporter
    from .utils.cache_helpers import clear_tx_cache

    User = get_user_model()
    user = User.objects.get(pk=user_id)
    df = pd.read_excel(file_path)
    importer = BulkTransactionImporter(user, batch_size=5000)
    result = importer.import_dataframe(df)
    clear_tx_cache(user.id, force=True)
    Path(file_path).unlink(missing_ok=True)
    return result


@shared_task
def estimate_all_transactions_task(user_id=None, period=None, dry_run=False):
    """Run heavy estimation across users and periods."""
    from core.management.commands.estimate_all_transactions import Command

    cmd = Command()
    options = {}
    if user_id:
        options["user_id"] = user_id
    if period:
        options["period"] = period
    if dry_run:
        options["dry_run"] = True
    cmd.handle(**options)


@shared_task
def sync_monthly_summaries_task(all=False, period=None):
    """Recalculate monthly summaries for analytics."""
    from core.management.commands.sync_monthly_summaries import Command

    cmd = Command()
    options = {}
    if all:
        options["all"] = True
    if period:
        options["period"] = period
    cmd.handle(**options)
