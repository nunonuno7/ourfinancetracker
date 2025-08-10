
from django.test import TestCase, Client

class HealthzTests(TestCase):
    def test_healthz_ok(self):
        client = Client()
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.content == b"ok"
        assert "no-store" in r.get("Cache-Control", "")
