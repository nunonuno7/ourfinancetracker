import re
from django.test import Client, SimpleTestCase
from django.conf import settings


class TestCSPHeaders(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def _get_ok_url(self):
        # Prefer a cheap endpoint that returns 200 without auth.
        # Use /healthz/ if it exists; fallback to "/" otherwise.
        for url in ("/healthz/", "/"):
            resp = self.client.get(url)
            if resp.status_code < 500:
                return url
        # As a last resort, still use root
        return "/"

    def test_csp_header_contains_upgrade_insecure_requests(self):
        url = self._get_ok_url()
        resp = self.client.get(url)
        csp = resp.headers.get("Content-Security-Policy")

        assert csp, "Missing Content-Security-Policy header"
        # Must include the bare flag (with or without trailing semicolon)
        assert "upgrade-insecure-requests" in csp, csp
        # Must NOT include invalid value formatting
        assert "upgrade-insecure-requests True" not in csp
        assert "upgrade-insecure-requests 'True'" not in csp

    def test_csp_header_no_invalid_nonce_in_directive(self):
        url = self._get_ok_url()
        resp = self.client.get(url)
        csp = resp.headers.get("Content-Security-Policy")
        assert csp
        # Disallow invalid/unknown directive seen previously
        assert "nonce-in" not in csp

    def test_csp_header_emitted_once(self):
        url = self._get_ok_url()
        resp = self.client.get(url)
        # Django merges duplicate headers; to be safe ensure we only have one effective header
        # (framework exposes the final string; this asserts that our policy string contains only one policy block)
        csp = resp.headers.get("Content-Security-Policy")
        assert csp
        # Heuristic: count occurrences of 'default-src' or the final semicolon blocks
        assert csp.count("default-src") == 1, f"CSP appears duplicated: {csp}"

