
from django.test import TestCase

class HealthzTests(TestCase):
    def test_healthz_ok(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertIn("no-store", response.get("Cache-Control", ""))
