from django.db import migrations, models
from django.contrib.postgres.operations import AddIndexConcurrently

class Migration(migrations.Migration):
    atomic = False  # Necessário para índices concorrentes [1][8]
    
    dependencies = [
        ('core', '0004_alter_dateperiod_month'),  # Substitui pelo último número da tua migração
    ]

    operations = [
        AddIndexConcurrently(
            model_name='transaction',
            index=models.Index(
                fields=['user_id', '-date'],
                name='idx_transaction_user_date'
            ),
        ),
        AddIndexConcurrently(
            model_name='accountbalance',
            index=models.Index(
                fields=['account_id', 'period_id'],
                name='idx_accountbalance_account_period'
            ),
        ),
        AddIndexConcurrently(
            model_name='transaction',
            index=models.Index(
                fields=['period_id', 'type'],
                name='idx_transaction_period_type'
            ),
        ),
    ]
