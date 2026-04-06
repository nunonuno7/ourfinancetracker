from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import (
    Account,
    AccountBalance,
    AccountType,
    Category,
    DatePeriod,
    Transaction,
    get_default_currency,
)


class TestDashboardExportPage(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="exporter", password="p")
        self.client.force_login(self.user)

        self.currency = get_default_currency()
        self.savings_type = AccountType.objects.get_or_create(name="Savings")[0]
        self.investment_type = AccountType.objects.get_or_create(name="Investments")[0]
        self.checking_type = AccountType.objects.get_or_create(name="Checking")[0]

        self.savings_account = Account.objects.create(
            user=self.user,
            name="Emergency Fund",
            account_type=self.savings_type,
            currency=self.currency,
        )
        self.investment_account = Account.objects.create(
            user=self.user,
            name="Brokerage",
            account_type=self.investment_type,
            currency=self.currency,
        )
        self.checking_account = Account.objects.create(
            user=self.user,
            name="Main Checking",
            account_type=self.checking_type,
            currency=self.currency,
        )

        self.jan = DatePeriod.objects.create(year=2024, month=1, label="Jan 2024")
        self.feb = DatePeriod.objects.create(year=2024, month=2, label="Feb 2024")
        self.mar = DatePeriod.objects.create(year=2024, month=3, label="Mar 2024")

        AccountBalance.objects.create(
            account=self.savings_account,
            period=self.jan,
            reported_balance=Decimal("1000"),
        )
        AccountBalance.objects.create(
            account=self.investment_account,
            period=self.jan,
            reported_balance=Decimal("5000"),
        )
        AccountBalance.objects.create(
            account=self.checking_account,
            period=self.jan,
            reported_balance=Decimal("700"),
        )
        AccountBalance.objects.create(
            account=self.savings_account,
            period=self.feb,
            reported_balance=Decimal("1300"),
        )
        AccountBalance.objects.create(
            account=self.investment_account,
            period=self.feb,
            reported_balance=Decimal("5600"),
        )
        AccountBalance.objects.create(
            account=self.checking_account,
            period=self.feb,
            reported_balance=Decimal("900"),
        )
        AccountBalance.objects.create(
            account=self.savings_account,
            period=self.mar,
            reported_balance=Decimal("2000"),
        )

        self.food = Category.objects.create(user=self.user, name="Food")
        self.travel = Category.objects.create(user=self.user, name="Travel")

        Transaction.objects.create(
            user=self.user,
            date=date(2024, 1, 10),
            period=self.jan,
            type=Transaction.Type.INCOME,
            amount=Decimal("2500"),
            account=self.checking_account,
        )
        Transaction.objects.create(
            user=self.user,
            date=date(2024, 1, 11),
            period=self.jan,
            type=Transaction.Type.EXPENSE,
            amount=Decimal("-800"),
            category=self.food,
            account=self.checking_account,
        )
        Transaction.objects.create(
            user=self.user,
            date=date(2024, 2, 5),
            period=self.feb,
            type=Transaction.Type.INVESTMENT,
            amount=Decimal("300"),
            account=self.investment_account,
        )
        Transaction.objects.create(
            user=self.user,
            date=date(2024, 2, 12),
            period=self.feb,
            type=Transaction.Type.EXPENSE,
            amount=Decimal("-650"),
            category=self.food,
            account=self.checking_account,
            is_estimated=True,
        )
        Transaction.objects.create(
            user=self.user,
            date=date(2024, 3, 2),
            period=self.mar,
            type=Transaction.Type.EXPENSE,
            amount=Decimal("-1200"),
            category=self.travel,
            account=self.checking_account,
        )

    def test_dashboard_export_renders_clean_report_for_selected_range(self):
        response = self.client.get(
            reverse("dashboard_export"),
            {"start_period": "2024-01", "end_period": "2024-02"},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        self.assertIn("Financial Export", html)
        self.assertIn("Monthly Performance", html)
        self.assertIn("Detailed Balance Matrix", html)
        self.assertIn("Expense Breakdown", html)
        self.assertIn("Latest Account Snapshot", html)
        self.assertIn("Emergency Fund", html)
        self.assertIn("Main Checking", html)
        self.assertIn("Food", html)
        self.assertNotIn("Travel", html)
