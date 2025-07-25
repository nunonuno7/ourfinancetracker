# Generated by Django 5.1.4 on 2025-06-30 00:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_adjustment_constraints"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="transaction",
            name="unique_adjustment_per_user_period",
        ),
        migrations.AlterField(
            model_name="transaction",
            name="type",
            field=models.CharField(
                choices=[
                    ("EX", "Expense"),
                    ("IN", "Income"),
                    ("IV", "Investment"),
                    ("TR", "Transfer"),
                ],
                max_length=2,
            ),
        ),
    ]
