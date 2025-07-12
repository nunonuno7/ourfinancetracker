
# Generated adjustment constraints migration

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_alter_dateperiod_year_alter_transaction_editable_and_more'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='transaction',
            constraint=models.UniqueConstraint(
                condition=models.Q(type='AJ'),
                fields=['user', 'period'],
                name='unique_adjustment_per_user_period'
            ),
        ),
    ]
