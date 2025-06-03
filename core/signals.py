from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import now
from django.contrib.auth import get_user_model

from .models import Transaction, Account, AccountType, Currency

User = get_user_model()


@receiver(post_save, sender=Transaction)
def update_transaction_status(sender, instance, created, **kwargs):
    # Aqui podes fazer algo após uma transação ser criada
    if created and instance.type == Transaction.Type.EXPENSE:
        print(f"New expense created: {instance}")


@receiver(post_save, sender=User)
def create_default_account(sender, instance, created, **kwargs):
    if not created:
        return

    if not Account.objects.filter(user=instance, name__iexact="Cash").exists():
        acc_type = AccountType.objects.filter(name__iexact="Saving").first()
        currency = Currency.objects.filter(code__iexact="EUR").first()

        Account.objects.create(
            user=instance,
            name="Cash",
            account_type=acc_type,
            currency=currency,
            created_at=now()
        )
