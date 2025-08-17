from django.test import Client, SimpleTestCase


class TestPermissionsPolicyHeader(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def _get_ok_url(self):
        for url in ("/healthz", "/"):
            resp = self.client.get(url)
            if resp.status_code < 500:
                return url
        return "/"

    def test_permissions_policy_header_present(self):
        url = self._get_ok_url()
        resp = self.client.get(url)
        policy = resp.headers.get("Permissions-Policy")
        assert policy, "Missing Permissions-Policy header"
        for feature in ("camera=()", "microphone=()", "geolocation=()"):
            assert feature in policy, policy
