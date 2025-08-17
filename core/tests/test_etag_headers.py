import json
from decimal import Decimal
from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from core.models import Transaction


class ETagHeadersTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("etaguser", "etag@example.com", "pass")
        self.client.force_login(self.user)
        Transaction.objects.create(user=self.user, date=date(2024, 1, 1), amount=Decimal("10.00"), type="IN")

    def test_transactions_json_etag(self):
        url = reverse("transactions_json")
        params = {"date_start": "2024-01-01", "date_end": "2024-12-31"}
        response = self.client.get(url, params)
        self.assertIn("ETag", response)
        self.assertIn("Last-Modified", response)
        etag = response["ETag"]
        last_mod = response["Last-Modified"]
        response_304 = self.client.get(url, params, HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(response_304.status_code, 304)
        response_304_lm = self.client.get(url, params, HTTP_IF_MODIFIED_SINCE=last_mod)
        self.assertEqual(response_304_lm.status_code, 304)

    def test_transactions_totals_v2_etag(self):
        url = reverse("transactions_totals_v2")
        payload = {
            "date_start": "2024-01-01",
            "date_end": "2024-12-31",
            "include_system": False,
        }
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json")
        self.assertIn("ETag", response)
        self.assertIn("Last-Modified", response)
        etag = response["ETag"]
        last_mod = response["Last-Modified"]
        response_304 = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_IF_NONE_MATCH=etag,
        )
        self.assertEqual(response_304.status_code, 304)
        response_304_lm = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_IF_MODIFIED_SINCE=last_mod,
        )
        self.assertEqual(response_304_lm.status_code, 304)
