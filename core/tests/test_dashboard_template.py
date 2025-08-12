from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils.timezone import now
from unittest.mock import patch


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
        self.assertIn('Verification:', html)
        self.assertNotIn('{% include', html)
