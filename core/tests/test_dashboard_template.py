import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils.timezone import now

from core.models import (
    Account,
    AccountBalance,
    AccountType,
    DatePeriod,
    Transaction,
    get_default_currency,
)


class TestDashboardTemplate(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")
        self.client.force_login(self.user)

    @patch(
        "core.views.DashboardView.get_context_data",
        return_value={
            "periods": [],
            "kpis": {"verified_expenses_pct": 0, "verification_level": "Moderate"},
        },
    )
    def test_verified_expenses_card_renders(self, mocked_ctx):
        url = reverse("dashboard")
        resp = self.client.get(url, secure=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('id="verified-expenses"', html)
        self.assertIn('id="verified-progress"', html)
        self.assertIn("Verification:", html)
        self.assertNotIn("{% include", html)

    @patch(
        "core.views.DashboardView.get_context_data",
        return_value={
            "periods": [],
            "kpis": {"verified_expenses_pct": 0, "verification_level": "Moderate"},
        },
    )
    def test_average_investment_card_renders(self, mocked_ctx):
        url = reverse("dashboard")
        resp = self.client.get(url, secure=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("Average Investment", html)
        self.assertIn('id="average-investment"', html)

    def test_dashboard_template_snapshot(self):
        factory = RequestFactory()
        request = factory.get("/")
        request.user = AnonymousUser()
        request.csp_nonce = ""
        context = {
            "periods": [],
            "kpis": {"verified_expenses_pct": 0, "verification_level": "Moderate"},
        }
        html = render_to_string("core/dashboard.html", context, request=request)
        match = re.search(
            r'(<div class="card border-info h-100 kpi-card".*?id="verified-expenses".*?</small>\s*</div>\s*</div>)',
            html,
            re.DOTALL,
        )
        assert match, "Verified expenses card not found"
        snippet = match.group(1).strip()
        snapshot_dir = Path(__file__).resolve().parent / "snapshots"
        snapshot_dir.mkdir(exist_ok=True)
        snapshot_file = snapshot_dir / "verified_expenses_card.html"
        if not snapshot_file.exists():
            snapshot_file.write_text(snippet, encoding="utf-8")
            self.fail("Snapshot file created; verify contents and rerun tests.")
        self.assertEqual(snippet, snapshot_file.read_text(encoding="utf-8"))


class TestDashboardView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="history-user", password="p")
        self.client.force_login(self.user)

        self.currency = get_default_currency()
        self.savings_type = AccountType.objects.get_or_create(name="Savings")[0]
        self.account = Account.objects.create(
            user=self.user,
            name="Savings Account",
            account_type=self.savings_type,
            currency=self.currency,
        )

        self.jan = DatePeriod.objects.create(year=2024, month=1, label="Jan 2024")
        self.feb = DatePeriod.objects.create(year=2024, month=2, label="Feb 2024")

    def test_dashboard_history_renders_with_multiple_periods(self):
        AccountBalance.objects.create(
            account=self.account,
            period=self.jan,
            reported_balance=Decimal("500"),
        )
        AccountBalance.objects.create(
            account=self.account,
            period=self.feb,
            reported_balance=Decimal("800"),
        )

        Transaction.objects.create(
            user=self.user,
            date=date(2024, 1, 10),
            period=self.jan,
            type=Transaction.Type.INCOME,
            amount=Decimal("1000"),
            account=self.account,
        )
        Transaction.objects.create(
            user=self.user,
            date=date(2024, 2, 10),
            period=self.feb,
            type=Transaction.Type.INCOME,
            amount=Decimal("1200"),
            account=self.account,
        )

        response = self.client.get(reverse("dashboard"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="verified-expenses"')
