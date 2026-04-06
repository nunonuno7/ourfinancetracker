import os

# Provide a deterministic secret key so tests can run without requiring an
# external environment configuration.  This key is suitable only for tests.
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from .settings import *  # inherit base settings

# --- Database: prefer an explicit test DB URL, otherwise keep SQLite tests ---
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_DATABASE_URL and dj_database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            TEST_DATABASE_URL,
            conn_max_age=0,
            ssl_require=False,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "testdb.sqlite3",
        }
    }

# --- Email: in-memory so tests don't hit real SMTP ---
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Live-server browser smoke tests can issue multiple concurrent requests from
# the same browser page. Using signed-cookie sessions avoids SQLite session-table
# locking/thread-safety edge cases while keeping the normal test suite unchanged.
if os.environ.get("RUN_BROWSER_SMOKE") == "1":
    SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

# --- Caches: local memory to avoid external dependencies ---
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "oft-test-cache",
    }
}

# --- Speed up auth hashing in tests ---
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# --- Safety: never keep persistent DB connections in tests ---
CONN_MAX_AGE = 0

# --- Optional: make tests deterministic & quiet noisy integrations ---
DEBUG = False
SECURE_SSL_REDIRECT = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
AXES_LOCKOUT_HTTP_RESPONSE_CODE = 200
AXES_HTTP_RESPONSE_CODE = 200

# Ensure CSP middleware emits the upgrade directive during tests
CONTENT_SECURITY_POLICY["DIRECTIVES"]["upgrade-insecure-requests"] = []

# Allow Django test client host
ALLOWED_HOSTS.append("testserver")
