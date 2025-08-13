import json
from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from core.models import Transaction


class TransactionsTotalsV2Test(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("tester", "tester@example.com", "pass")
        self.client.force_login(self.user)

    def test_totals_respect_signs_and_decimals(self):
        # Income with a refund
        Transaction.objects.create(user=self.user, date=date(2024, 1, 5), amount=Decimal("100.10"), type="IN")
        Transaction.objects.create(user=self.user, date=date(2024, 1, 7), amount=Decimal("-20.00"), type="IN")
        # Expenses with a refund
        Transaction.objects.create(user=self.user, date=date(2024, 1, 10), amount=Decimal("30.05"), type="EX")
        Transaction.objects.create(user=self.user, date=date(2024, 1, 12), amount=Decimal("-5.00"), type="EX")
        # Investments in and out
        Transaction.objects.create(user=self.user, date=date(2024, 1, 15), amount=Decimal("50.00"), type="IV")
        Transaction.objects.create(user=self.user, date=date(2024, 1, 20), amount=Decimal("-10.00"), type="IV")

        url = reverse("transactions_totals_v2")
        response = self.client.post(
            url,
            data=json.dumps({
                "date_start": "2024-01-01",
                "date_end": "2024-01-31",
                "include_system": False,
            }),
            content_type="application/json",
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertAlmostEqual(data["income"], 80.10)
        self.assertAlmostEqual(data["expenses"], 25.05)
        self.assertAlmostEqual(data["investments"], 40.00)
        self.assertAlmostEqual(data["balance"], 55.05)
