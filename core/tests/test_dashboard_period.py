from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import DatePeriod, Transaction


class TestDashboardPeriodMode(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")
        self.client.force_login(self.user)

        period = DatePeriod.objects.create(year=2025, month=1)
        Transaction.objects.create(
            user=self.user,
            date=date(2025, 1, 1),
            period=period,
            amount=100,
            type=Transaction.Type.INCOME,
        )
        Transaction.objects.create(
            user=self.user,
            date=date(2025, 1, 2),
            period=period,
            amount=50,
            type=Transaction.Type.EXPENSE,
        )

    def test_period_kpis_render(self):
        url = reverse("dashboard")
        resp = self.client.get(url, {"mode": "period", "period": "2025-01"}, secure=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("Income", html)
        self.assertIn("Expenses", html)

