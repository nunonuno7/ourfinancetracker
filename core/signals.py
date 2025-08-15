# core/signals.py

from django.dispatch import receiver
from django.utils.timezone import now
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, post_delete, pre_delete
from django.db import transaction
from django.core.cache import cache
from decimal import Decimal

from .models import (
    Transaction,
    Account,
    AccountBalance,
    AccountType,
    Currency,
    UserSettings,
    DatePeriod,
    FxRate,
)
from core.utils.cache_helpers import clear_tx_cache
import logging
from datetime import date

logger = logging.getLogger(__name__)

User = get_user_model()

# ──────────────────────────── Transações ─────────────────────────────

@receiver(post_save, sender=Transaction)
def update_transaction_status(sender, instance, created, **kwargs):
    """
    Mensagem de debug ao criar uma nova despesa.
    """
    if created and instance.type == Transaction.Type.EXPENSE:
        logger.debug(f"🧾 Nova despesa criada: {instance}")

@receiver(post_save, sender=Transaction)
@receiver(post_delete, sender=Transaction) 
def clear_transaction_cache(sender, instance, **kwargs):
    """Limpar cache quando transações mudam."""
    # Evitar loop infinito - só limpar se não estamos já a processar
    if hasattr(clear_transaction_cache, '_processing'):
        return

    # 🚫 PROTEÇÃO EXTRA: Não processar transações automáticas do sistema
    if getattr(instance, 'is_system', False):
        logger.debug(f"🚫 Saltando processamento de transação automática do sistema para user_id={instance.user_id}")
        return

    # Skip cache clearing during bulk operations (will be handled by bulk views)
    from django.db import transaction as db_transaction
    if db_transaction.get_connection().in_atomic_block:
        logger.debug(f"🚫 Saltando limpeza de cache durante operação atómica para user_id={instance.user_id}")
        return

    try:
        clear_transaction_cache._processing = True
        logger.debug(f"🧹 Sinal ativado — limpando cache para user_id={instance.user_id}")
        clear_tx_cache(instance.user_id)
        cache.clear()
    finally:
        delattr(clear_transaction_cache, '_processing')

# 🚫 REMOVIDO: Armazenamento de dados para atualização automática de saldos

# 🚫 REMOVIDO: Signals que alteravam saldos automaticamente
# Os saldos das contas devem ser controlados APENAS pelo utilizador

# ───────────────────────────── Utilizador ─────────────────────────────

@receiver(post_save, sender=User)
def create_default_account(sender, instance, created, **kwargs):
    """
    Cria uma conta 'Cash' automaticamente para o utilizador, se ainda não existir.
    Também garante que o utilizador tem `UserSettings`.
    """
    if not created:
        return

    # Garantir que o utilizador tem settings
    settings, _ = UserSettings.objects.get_or_create(user=instance)

    # Criar conta "Cash" se ainda não existir
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


@receiver(post_save, sender=FxRate)
def clear_cache_on_fx_rate(sender, instance, **kwargs):
    """Invalidate cached FX rates and KPI aggregates when rates change."""
    # Remove direct and inverse FX cache entries for the affected pair
    cache.delete(f"fx:{instance.date}:{instance.base.code}:{instance.quote.code}")
    cache.delete(f"fx:{instance.date}:{instance.quote.code}:{instance.base.code}")

    # Clear any cached KPI aggregates – iterate over known keys when possible
    try:
        for key in list(cache._cache.keys()):
            if "kpi:" in str(key):
                cache.delete(str(key).split(":", 2)[-1])
    except Exception:
        # Fallback for cache backends without key inspection support
        cache.clear()
