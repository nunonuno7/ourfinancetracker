import json
import os
from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Transaction


class ETagHeadersTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("etaguser", "etag@example.com", "pass")
        self.client.force_login(self.user)
        Transaction.objects.create(
            user=self.user, date=date(2024, 1, 1), amount=Decimal("10.00"), type="IN"
        )

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
        response = self.client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )
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

    @mock.patch.dict(
        os.environ,
        {
            "SUPABASE_REST_URL": "http://test",
            "SUPABASE_API_KEY": "key",
            "SUPABASE_JWT_SECRET": "secret",
        },
    )
    @mock.patch("core.views.requests.post")
    @mock.patch("core.views.requests.get")
    def test_transactions_json_v2_etag(self, mock_get, mock_post):
        tx_resp = mock.Mock()
        tx_resp.json.return_value = [
            {
                "id": 1,
                "date": "2024-01-01",
                "type": "IN",
                "amount": 10,
                "category": {"name": "Cat"},
                "account": {"name": "Acc"},
                "period": "2024-01",
                "description": "d",
                "tags": "",
                "is_system": False,
                "editable": True,
                "is_estimated": False,
            }
        ]
        tx_resp.headers = {"Content-Range": "0-0/1"}
        tx_resp.raise_for_status = lambda: None
        mock_get.return_value = tx_resp

        filt_resp = mock.Mock()
        filt_resp.json.return_value = {
            "types": ["Income"],
            "categories": ["Cat"],
            "accounts": ["Acc"],
            "periods": ["2024-01"],
        }
        filt_resp.raise_for_status = lambda: None
        mock_post.return_value = filt_resp

        url = reverse("transactions_json_v2")
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
