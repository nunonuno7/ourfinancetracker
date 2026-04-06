# core/signals.py

from django.dispatch import receiver
from django.utils.timezone import now
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, post_delete, pre_delete
from django.db import transaction
from decimal import Decimal

from .models import Transaction, Account, AccountBalance, AccountType, Currency, UserSettings, DatePeriod
from core.utils.cache_helpers import clear_tx_cache
import logging
from datetime import date

logger = logging.getLogger(__name__)

User = get_user_model()

# ---------------------------- Transactions ----------------------------

@receiver(post_save, sender=Transaction)
def update_transaction_status(sender, instance, created, **kwargs):
    """
    Debug message when a new expense is created.
    """
    if created and instance.type == Transaction.Type.EXPENSE:
        logger.debug(f"New expense created: {instance}")

@receiver(post_save, sender=Transaction)
@receiver(post_delete, sender=Transaction) 
def clear_transaction_cache(sender, instance, **kwargs):
    """Clear cache when transactions change."""
    # Avoid infinite loops and only clear once per processing cycle
    if hasattr(clear_transaction_cache, "_processing"):
        return

    # Extra protection: skip system-generated transactions
    if getattr(instance, "is_system", False):
        logger.debug(
            f"Skipping system transaction processing for user_id={instance.user_id}"
        )
        return

    # Skip cache clearing during bulk operations (will be handled by bulk views)
    from django.db import transaction as db_transaction

    if db_transaction.get_connection().in_atomic_block:
        logger.debug(
            f"Skipping cache clearing during atomic operation for user_id={instance.user_id}"
        )
        return

    try:
        clear_transaction_cache._processing = True
        logger.debug(f"Signal triggered - clearing cache for user_id={instance.user_id}")
        clear_tx_cache(instance.user_id)
    finally:
        delattr(clear_transaction_cache, "_processing")

# Removed: storing data for automatic balance updates

# Removed: signals that changed balances automatically
# Account balances should only be controlled by the user

# ------------------------------- User --------------------------------

@receiver(post_save, sender=User)
def create_default_account(sender, instance, created, **kwargs):
    """
    Create a "Cash" account automatically for the user if it does not exist yet.
    Also ensure the user has `UserSettings`.
    """
    if not created:
        return

    # Ensure the user has settings
    settings, _ = UserSettings.objects.get_or_create(user=instance)

    # Create the "Cash" account if it does not already exist
    if not Account.objects.filter(user=instance, name__iexact="Cash").exists():
        acc_type = AccountType.objects.filter(name__iexact="Savings").first()
        currency = settings.default_currency or Currency.objects.filter(code="EUR").first()

        Account.objects.create(
            user=instance,
            name="Cash",
            account_type=acc_type,
            currency=currency,
            created_at=now()
        )
