
# Generated migration to remove investment_flow field

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_add_account_indexes'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='transaction',
            name='investment_flow',
        ),
    ]
