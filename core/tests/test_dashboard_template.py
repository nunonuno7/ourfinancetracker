import re
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils.timezone import now


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
            snapshot_file.write_text(snippet)
            self.fail("Snapshot file created; verify contents and rerun tests.")
        self.assertEqual(snippet, snapshot_file.read_text())
