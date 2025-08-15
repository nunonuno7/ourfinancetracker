from .settings import *  # inherit base settings

# --- Database: SQLite for tests (no Supabase, no Pooler) ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "testdb.sqlite3",
    }
}

# --- Email: in-memory so tests don't hit real SMTP ---
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

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
CSP_UPGRADE_INSECURE_REQUESTS = True
CSP_REPORT_ONLY = False

# Allow Django test client host
ALLOWED_HOSTS.append("testserver")
