from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Transaction


class TestDashboardInvestmentKPI(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            "tester",
            "tester@example.com",
            "pass",
        )
        self.client.force_login(self.user)

    def test_average_investment_includes_withdrawals(self):
        Transaction.objects.create(
            user=self.user,
            date=date(2024, 1, 10),
            amount=Decimal("100"),
            type="IV",
        )
        Transaction.objects.create(
            user=self.user,
            date=date(2024, 1, 15),
            amount=Decimal("-150"),
            type="IV",
        )

        url = reverse("dashboard_kpis_json")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        avg = float(
            data["valor_investido_medio"]
            .replace("€", "")
            .replace(",", "")
            .strip()  # noqa: E501
        )
        self.assertEqual(avg, -50.0)
