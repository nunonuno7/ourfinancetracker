# core/signals.py

from django.dispatch import receiver
from django.utils.timezone import now
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from .models import Transaction, Account, AccountType, Currency, UserSettings

from .models import Transaction, Account, AccountType, Currency
from core.cache import TX_LAST

User = get_user_model()

# ───────────── Transações: Mensagem ao criar uma despesa ─────────────
@receiver(post_save, sender=Transaction)
def update_transaction_status(sender, instance, created, **kwargs):
    if created and instance.type == Transaction.Type.EXPENSE:
        print(f"🧾 Nova despesa criada: {instance}")

# ───────────── Utilizador: Criar conta "Cash" por omissão ─────────────
@receiver(post_save, sender=User)
def create_default_account(sender, instance, created, **kwargs):
    if not created:
        return

    # Garantir que o utilizador tem settings
    settings, _ = UserSettings.objects.get_or_create(user=instance)

    # Criar conta "Cash" se ainda não existir
    if not Account.objects.filter(user=instance, name__iexact="Cash").exists():
        acc_type = AccountType.objects.filter(name__iexact="Saving").first() 
        currency = settings.default_currency or Currency.objects.filter(code="EUR").first()

        Account.objects.create(
            user=instance,
            name="Cash",
            account_type=acc_type,
            currency=currency,
            created_at=now()
        )


# ───────────── Transações: Limpeza do cache JSON ─────────────
@receiver([post_save, post_delete], sender=Transaction)
def clear_transaction_cache(sender, instance, **kwargs):
    """Limpa o cache de transações do utilizador quando são alteradas."""
    user_id = instance.user_id
    if user_id in TX_LAST:
        print(f"🧹 Cache limpa para user_id={user_id}")
        del TX_LAST[user_id]