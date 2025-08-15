from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0014_alter_tag_category_alter_transaction_editable_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='RecurringTransaction',
        ),
        migrations.CreateModel(
            name='RecurringTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('schedule', models.CharField(choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')], max_length=10)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('next_run_at', models.DateTimeField()),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='recurring_transactions', to='core.account')),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='recurring_templates', to='core.category')),
                ('user', models.ForeignKey(on_delete=models.CASCADE, related_name='recurring_transactions', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='recurringtransaction',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='recurring_transactions', to='core.tag'),
        ),
    ]
