from django.test import TestCase
from django.conf import settings


class SecurityHeadersTests(TestCase):
    def test_cross_origin_headers(self):
        response = self.client.get("/admin/login/", secure=True)
        self.assertEqual(response.headers.get("Cross-Origin-Opener-Policy"), "same-origin")

    def test_http_only_cookies_enabled(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
