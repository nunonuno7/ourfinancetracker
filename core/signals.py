# core/signals.py

from django.dispatch import receiver
from django.utils.timezone import now
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from .models import Transaction, Account, AccountType, Currency, UserSettings

from .models import Transaction, Account, AccountType, Currency

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
        acc_type = AccountType.objects.filter(name__iexact="Saving").first() or AccountType.objects.first()
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
    user_id = instance.user_id
    key_list_name = f"transactions_json_keys_user_{user_id}"

    # 🔎 Obtém a lista de chaves de cache associadas ao utilizador
    keys = cache.get(key_list_name, [])

    for key in keys:
        cache.delete(key)
        print(f"🧹 Cache limpa: {key}")

    # 🧼 Limpa também o registo da lista de chaves
    cache.delete(key_list_name)
