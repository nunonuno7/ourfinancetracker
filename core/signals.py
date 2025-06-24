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

    # Skip cache clearing during bulk operations (will be handled by bulk views)
    from django.db import transaction as db_transaction
    if db_transaction.get_connection().in_atomic_block:
        logger.debug(f"🚫 Saltando limpeza de cache durante operação atómica para user_id={instance.user_id}")
        return

    try:
        clear_transaction_cache._processing = True
        logger.debug(f"🧹 Sinal ativado — limpando cache para user_id={instance.user_id}")
        clear_tx_cache(instance.user_id)
    finally:
        delattr(clear_transaction_cache, '_processing')

# Store transaction data before deletion for cash update
_transaction_data_before_delete = {}

@receiver(pre_delete, sender=Transaction)
def store_transaction_before_delete(sender, instance, **kwargs):
    """Store transaction data before deletion for cash balance update."""
    _transaction_data_before_delete[instance.id] = {
        'user_id': instance.user_id,
        'amount': instance.amount,
        'type': instance.type,
        'date': instance.date,
        'period_id': instance.period_id
    }

@receiver(post_save, sender=Transaction)
def update_cash_balance_on_transaction_create(sender, instance, created, **kwargs):
    """
    Atualiza automaticamente o saldo da conta 'Cash' quando uma transação é criada ou editada.
    """
    if not created:
        return  # Skip updates for now

    try:
        with transaction.atomic():
            # Get or create Cash account
            cash_account = get_or_create_cash_account(instance.user)

            # Get the period for this transaction
            period = instance.period
            if not period:
                period, _ = DatePeriod.objects.get_or_create(
                    year=instance.date.year,
                    month=instance.date.month,
                    defaults={'label': instance.date.strftime('%B %Y')}
                )

            # Get current cash balance for this period
            cash_balance, created_balance = AccountBalance.objects.get_or_create(
                account=cash_account,
                period=period,
                defaults={'reported_balance': Decimal('0.00')}
            )

            # Update balance based on transaction type
            if instance.type == Transaction.Type.INCOME:
                cash_balance.reported_balance += instance.amount
                logger.info(f"💰 Cash +{instance.amount} (Income): {cash_balance.reported_balance}")
            elif instance.type == Transaction.Type.EXPENSE:
                cash_balance.reported_balance -= instance.amount
                logger.info(f"💸 Cash -{instance.amount} (Expense): {cash_balance.reported_balance}")
            elif instance.type == Transaction.Type.TRANSFER:
                # For transfers, we assume money is leaving cash (negative)
                cash_balance.reported_balance -= instance.amount
                logger.info(f"🔄 Cash -{instance.amount} (Transfer): {cash_balance.reported_balance}")
            # For INVESTMENT, we don't affect cash directly as it might be from another account

            cash_balance.save()

    except Exception as e:
        logger.error(f"❌ Erro ao atualizar saldo Cash: {e}")

@receiver(post_delete, sender=Transaction)
def update_cash_balance_on_transaction_delete(sender, instance, **kwargs):
    """
    Atualiza automaticamente o saldo da conta 'Cash' quando uma transação é eliminada.
    """
    try:
        # Get stored transaction data
        tx_data = _transaction_data_before_delete.get(instance.id)
        if not tx_data:
            logger.warning(f"⚠️ No stored data for deleted transaction {instance.id}")
            return

        with transaction.atomic():
            # Get Cash account
            try:
                cash_account = Account.objects.get(
                    user_id=tx_data['user_id'], 
                    name__iexact='Cash'
                )
            except Account.DoesNotExist:
                logger.warning(f"⚠️ Cash account not found for user {tx_data['user_id']}")
                return

            # Get the period
            try:
                period = DatePeriod.objects.get(id=tx_data['period_id'])
            except DatePeriod.DoesNotExist:
                period, _ = DatePeriod.objects.get_or_create(
                    year=tx_data['date'].year,
                    month=tx_data['date'].month,
                    defaults={'label': tx_data['date'].strftime('%B %Y')}
                )

            # Get cash balance for this period
            try:
                cash_balance = AccountBalance.objects.get(
                    account=cash_account,
                    period=period
                )
            except AccountBalance.DoesNotExist:
                logger.warning(f"⚠️ Cash balance not found for period {period}")
                return

            # Reverse the transaction effect
            if tx_data['type'] == Transaction.Type.INCOME:
                cash_balance.reported_balance -= tx_data['amount']
                logger.info(f"💰 Cash reversed -{tx_data['amount']} (Income deleted): {cash_balance.reported_balance}")
            elif tx_data['type'] == Transaction.Type.EXPENSE:
                cash_balance.reported_balance += tx_data['amount']
                logger.info(f"💸 Cash reversed +{tx_data['amount']} (Expense deleted): {cash_balance.reported_balance}")
            elif tx_data['type'] == Transaction.Type.TRANSFER:
                cash_balance.reported_balance += tx_data['amount']
                logger.info(f"🔄 Cash reversed +{tx_data['amount']} (Transfer deleted): {cash_balance.reported_balance}")

            cash_balance.save()

        # Clean up stored data
        if instance.id in _transaction_data_before_delete:
            del _transaction_data_before_delete[instance.id]

    except Exception as e:
        logger.error(f"❌ Erro ao reverter saldo Cash: {e}")

def get_or_create_cash_account(user):
    """
    Get or create the Cash account for a user.
    """
    try:
        return Account.objects.get(user=user, name__iexact='Cash')
    except Account.DoesNotExist:
        # Create Cash account
        account_type = AccountType.objects.filter(name__iexact='Savings').first()
        if not account_type:
            account_type = AccountType.objects.first()

        currency = Currency.objects.filter(code='EUR').first()
        if not currency:
            currency = Currency.objects.first()

        cash_account = Account.objects.create(
            user=user,
            name='Cash',
            account_type=account_type,
            currency=currency
        )

        logger.info(f"✅ Conta Cash criada automaticamente para {user.username}")
        return cash_account

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