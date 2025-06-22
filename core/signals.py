# core/signals.py

from django.dispatch import receiver
from django.utils.timezone import now
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, post_delete

from .models import Transaction, Account, AccountType, Currency, UserSettings
from core.utils.cache_helpers import clear_tx_cache
import logging
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

@receiver([post_save, post_delete], sender=Transaction)
def clear_transaction_cache(sender, instance, **kwargs):
    """
    Limpa a cache de transações (Django cache) sempre que uma transação
    é criada, atualizada ou eliminada.
    """
    user_id = instance.user_id
    logger.debug(f"🧹 Sinal ativado — limpando cache para user_id={user_id}")
    clear_tx_cache(user_id)

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