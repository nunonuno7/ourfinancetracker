
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from core.models import Transaction, AccountBalance
from core.models_monthly import MonthlySummary
from core.utils.date_helpers import period_str

def _touch(dt):
    """Mark period as dirty when transactions or balances change"""
    ms, _ = MonthlySummary.objects.get_or_create(period=period_str(dt))
    if not ms.is_dirty:
        ms.is_dirty = True
        ms.save(update_fields=["is_dirty", "updated_at"])

@receiver([post_save, post_delete], sender=Transaction)
def tx_changed(sender, instance, **kwargs):
    _touch(instance.date)

@receiver([post_save, post_delete], sender=AccountBalance)
def bal_changed(sender, instance, **kwargs):
    # AccountBalance uses period, convert to date
    from datetime import date
    period_date = date(instance.period.year, instance.period.month, 1)
    _touch(period_date)
