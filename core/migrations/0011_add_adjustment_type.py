
# Generated migration for adding Adjustment transaction type

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_remove_transaction_unique_adjustment_per_user_period_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='type',
            field=models.CharField(choices=[('EX', 'Expense'), ('IN', 'Income'), ('IV', 'Investment'), ('TR', 'Transfer'), ('AJ', 'Adjustment')], max_length=2),
        ),
    ]
