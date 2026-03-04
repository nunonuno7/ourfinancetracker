import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import DatePeriod, Tag, Transaction


class TransactionBulkDuplicateViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user("tester", "tester@example.com", "pass")
        self.client.force_login(self.user)
        self.url = reverse("transaction_bulk_duplicate")

    def test_bulk_duplicate_creates_requested_month_offsets_and_copies_tags(self):
        original_tx = Transaction.objects.create(
            user=self.user,
            type=Transaction.Type.EXPENSE,
            amount=Decimal("25.50"),
            date=date(2024, 1, 31),
            notes="Original",
        )
        food = Tag.objects.create(user=self.user, name="food")
        monthly = Tag.objects.create(user=self.user, name="monthly")
        original_tx.tags.add(food, monthly)

        response = self.client.post(
            self.url,
            data=json.dumps(
                {
                    "transaction_ids": [original_tx.id],
                    "months": [1, 2],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["created"], 2)
        self.assertEqual(data["months"], [1, 2])

        duplicated_dates = sorted(
            Transaction.objects.exclude(id=original_tx.id).values_list("date", flat=True)
        )
        self.assertEqual(duplicated_dates, [date(2024, 2, 29), date(2024, 3, 31)])

        feb_period = DatePeriod.objects.get(year=2024, month=2)
        mar_period = DatePeriod.objects.get(year=2024, month=3)
        self.assertEqual(feb_period.label, "February 2024")
        self.assertEqual(mar_period.label, "March 2024")

        duplicated_tags = [
            set(tx.tags.values_list("name", flat=True))
            for tx in Transaction.objects.exclude(id=original_tx.id)
        ]
        self.assertEqual(duplicated_tags, [{"food", "monthly"}, {"food", "monthly"}])

    def test_bulk_duplicate_rejects_invalid_months(self):
        original_tx = Transaction.objects.create(
            user=self.user,
            type=Transaction.Type.EXPENSE,
            amount=Decimal("10.00"),
            date=date(2024, 1, 10),
            notes="Original",
        )

        response = self.client.post(
            self.url,
            data=json.dumps(
                {
                    "transaction_ids": [original_tx.id],
                    "months": [0, 14],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("month offsets", data["error"])
        self.assertEqual(Transaction.objects.count(), 1)
