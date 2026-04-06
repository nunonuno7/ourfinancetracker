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

    def test_bulk_duplicate_creates_copy_in_selected_month_and_copies_tags(self):
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
                {"transaction_ids": [original_tx.id], "target_period": "2024-02"}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["created"], 1)
        self.assertEqual(data["target_period"], "2024-02")

        duplicate = Transaction.objects.exclude(id=original_tx.id).get()
        self.assertEqual(duplicate.date, date(2024, 2, 29))

        target_period = DatePeriod.objects.get(year=2024, month=2)
        self.assertEqual(duplicate.period, target_period)
        self.assertEqual(
            set(duplicate.tags.values_list("name", flat=True)),
            {"food", "monthly"},
        )

    def test_bulk_duplicate_requires_target_month(self):
        original_tx = Transaction.objects.create(
            user=self.user,
            type=Transaction.Type.EXPENSE,
            amount=Decimal("25.50"),
            date=date(2024, 1, 31),
        )

        response = self.client.post(
            self.url,
            data=json.dumps({"transaction_ids": [original_tx.id]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Target month is required")

    def test_bulk_duplicate_rejects_empty_selection(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"transaction_ids": [], "target_period": "2024-02"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "No transactions selected")

    def test_bulk_duplicate_supports_future_months(self):
        original_tx = Transaction.objects.create(
            user=self.user,
            type=Transaction.Type.EXPENSE,
            amount=Decimal("18.00"),
            date=date(2026, 4, 15),
            notes="April source",
        )

        response = self.client.post(
            self.url,
            data=json.dumps(
                {"transaction_ids": [original_tx.id], "target_period": "2026-08"}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["created"], 1)
        self.assertEqual(data["target_period"], "2026-08")

        duplicate = Transaction.objects.exclude(id=original_tx.id).get()
        self.assertEqual(duplicate.date, date(2026, 8, 15))
        self.assertEqual(duplicate.period.year, 2026)
        self.assertEqual(duplicate.period.month, 8)
