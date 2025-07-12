
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_transaction_editable_transaction_is_system_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_transaction_period_type_system ON core_transaction(period_id, type, is_system);",
            reverse_sql="DROP INDEX IF EXISTS idx_transaction_period_type_system;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_accountbalance_period_account_type ON core_accountbalance(period_id, account_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_accountbalance_period_account_type;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_account_user_type ON core_account(user_id, account_type_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_account_user_type;"
        ),
    ]
