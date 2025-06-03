from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Transaction

@receiver(post_save, sender=Transaction)
def update_transaction_status(sender, instance, created, **kwargs):
    # Aqui podes fazer algo após uma transação ser criada
    if created and instance.type == Transaction.Type.EXPENSE:
        print(f"New expense created: {instance}")
