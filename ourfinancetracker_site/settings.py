"""
Django settings.py — consolidated for DEV/PROD with Supabase Postgres,
CSP (django-csp), WhiteNoise, optional Redis, Debug Toolbar, and django-axes.
"""

from __future__ import annotations
import os
import warnings
from pathlib import Path
from dotenv import load_dotenv
from csp.constants import NONCE
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

try:
    import dj_database_url  # type: ignore
except ImportError:  # pragma: no cover
    dj_database_url = None

# ────────────────────────────────────────────────────
# Paths & .env
# ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
ENV = os.getenv

def env_bool(key: str, default: str = "false") -> bool:
    return ENV(key, default).lower() in {"1", "true", "yes", "on"}


def strtobool(val: str) -> bool:
    val = val.lower()
    if val in {"y", "yes", "t", "true", "on", "1"}:
        return True
    if val in {"n", "no", "f", "false", "off", "0"}:
        return False
    raise ValueError(f"invalid truth value {val}")

# ────────────────────────────────────────────────────
# Core flags & secret
# ────────────────────────────────────────────────────
DEBUG: bool = env_bool("DEBUG")
# If DEBUG is loaded from env as a string, normalize it
if isinstance(DEBUG, str):
    DEBUG = bool(strtobool(DEBUG))


SECRET_KEY = ENV("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required")

if not DEBUG:
    warnings.filterwarnings("ignore")

# ────────────────────────────────────────────────────
# Sentry (error monitoring)
# ────────────────────────────────────────────────────
SENTRY_DSN = ENV("SENTRY_DSN", "")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=float(ENV("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        profiles_sample_rate=float(ENV("SENTRY_PROFILES_SAMPLE_RATE", "0.0")),
        sample_rate=float(ENV("SENTRY_SAMPLE_RATE", "0.1")),
        send_default_pii=True,
    )

# ────────────────────────────────────────────────────
# Hosts & CSRF trusted origins
# ────────────────────────────────────────────────────
ALLOWED_HOSTS = [
    ".ourfinancetracker.com",
    ".onrender.com",
    ".replit.dev",
    "localhost",
    "127.0.0.1",
]

CSRF_TRUSTED_ORIGINS = [
    "https://ourfinancetracker.com",
    "https://www.ourfinancetracker.com",
    "http://localhost:8000", "http://localhost:8001",
    "http://127.0.0.1:8000", "http://127.0.0.1:8001",
    "http://localhost:3000", "http://127.0.0.1:3000",
]

def _extend_from_env_list(env_key: str, target_list: list[str], require_scheme: bool = False) -> None:
    raw = ENV(env_key, "") or ""
    if not raw:
        return
    for item in [x.strip() for x in raw.split(",") if x.strip()]:
        if require_scheme and not (item.startswith("http://") or item.startswith("https://")):
            continue
        target_list.append(item)

if ENV("REPLIT_DEV_DOMAIN"):
    dom = ENV("REPLIT_DEV_DOMAIN")
    ALLOWED_HOSTS.append(dom)
    CSRF_TRUSTED_ORIGINS += [f"https://{dom}", f"http://{dom}"]

_extend_from_env_list("EXTRA_ALLOWED_HOSTS", ALLOWED_HOSTS, require_scheme=False)
_extend_from_env_list("EXTRA_CSRF_TRUSTED_ORIGINS", CSRF_TRUSTED_ORIGINS, require_scheme=True)

# ────────────────────────────────────────────────────
# Apps & Middleware
# ────────────────────────────────────────────────────
INSTALLED_APPS = [
    # Django
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "django.contrib.sites",
    # Third-party
    "whitenoise.runserver_nostatic",
    "widget_tweaks",
    "django.contrib.humanize",
    "csp",
    "axes",
    "anymail",
    "django_celery_beat",
    # Project
    "accounts",
    "core",
]

SHOW_DEBUG_TOOLBAR = env_bool("SHOW_DEBUG_TOOLBAR")
if DEBUG and SHOW_DEBUG_TOOLBAR:
    INSTALLED_APPS += ["debug_toolbar"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "csp.middleware.CSPMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.log_filter.SuppressJsonLogMiddleware",
]
if DEBUG:
    MIDDLEWARE.append("core.middleware.performance.PerformanceMiddleware")
MIDDLEWARE.append("axes.middleware.AxesMiddleware")  # axes middleware must come last

if DEBUG and SHOW_DEBUG_TOOLBAR:
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
    INTERNAL_IPS = ["127.0.0.1"]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

ROOT_URLCONF = "ourfinancetracker_site.urls"
WSGI_APPLICATION = "ourfinancetracker_site.wsgi.application"

# ────────────────────────────────────────────────────
# Templates
# ────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "accounts" / "templates", BASE_DIR / "core" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.sentry_dsn",
            ],
        },
    }
]

# ────────────────────────────────────────────────────
# Database (Supabase preferred via SUPABASE_DB_URL/DATABASE_URL; fallback SQLite)
# ────────────────────────────────────────────────────
SUPA_URL = ENV("SUPABASE_DB_URL") or ENV("DATABASE_URL")
if not SUPA_URL and ENV("DB_HOST"):
    SUPA_URL = (
        f"postgresql://{ENV('DB_USER')}:{ENV('DB_PASSWORD')}"
        f"@{ENV('DB_HOST')}:{ENV('DB_PORT','5432')}/{ENV('DB_NAME')}"
    )

if SUPA_URL and dj_database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            SUPA_URL,
            conn_max_age=int(ENV("DB_CONN_MAX_AGE", "600")),
            ssl_require=not DEBUG,
        )
    }
else:
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
    }

# ────────────────────────────────────────────────────
# Cache (optional Redis)
# ────────────────────────────────────────────────────
if ENV("REDIS_URL"):
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": ENV("REDIS_URL"),
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "KEY_PREFIX": "ourft",
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "ourft-cache"}}

# ────────────────────────────────────────────────────
# I18N
# ────────────────────────────────────────────────────
LANGUAGE_CODE = "en-gb"
TIME_ZONE = ENV("TIME_ZONE", "Europe/Lisbon")
USE_I18N = True
USE_TZ = True

# ────────────────────────────────────────────────────
# Static & Media (WhiteNoise)
# ────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "core" / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = (
    "django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG
    else "whitenoise.storage.CompressedManifestStaticFilesStorage"
)
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = DEBUG

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ────────────────────────────────────────────────────
# Auth / misc
# ────────────────────────────────────────────────────
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SITE_ID = 1

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ────────────────────────────────────────────────────
# Security profiles (DEV/PROD): HTTPS, Cookies/CSRF, and CSP
# ────────────────────────────────────────────────────
# --- CSP base policy ---
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ("'self'",),
        "script-src": (
            "'self'",
            NONCE,
            "https://cdn.jsdelivr.net",
            "https://cdn.datatables.net",
            "https://cdnjs.cloudflare.com",
            "https://code.jquery.com",
            "https://browser.sentry-cdn.com",
        ),
        "style-src": (
            "'self'",
            NONCE,
            "https://cdn.jsdelivr.net",
            "https://cdn.datatables.net",
            "https://cdnjs.cloudflare.com",
            "https://code.jquery.com",
        ),
        "img-src": ("'self'", "data:"),
        "connect-src": ("'self'", "https://*.ingest.sentry.io"),
        "font-src": (
            "'self'",
            "https://cdn.jsdelivr.net",
            "https://cdnjs.cloudflare.com",
        ),
        "object-src": ("'none'",),
        "base-uri": ("'self'",),
    }
}

if not DEBUG:
    CONTENT_SECURITY_POLICY["DIRECTIVES"]["upgrade-insecure-requests"] = []

SESSION_COOKIE_SAMESITE = ENV("SESSION_COOKIE_SAMESITE", "Strict")
CSRF_COOKIE_SAMESITE = ENV("CSRF_COOKIE_SAMESITE", "Strict")

if DEBUG:
    # Dev: no forced HTTPS
    SECURE_SSL_REDIRECT = False
    SECURE_PROXY_SSL_HEADER = None

    # Cookies & CSRF over HTTP
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    CSRF_COOKIE_HTTPONLY = False
    CSRF_USE_SESSIONS = False
    CSRF_FAILURE_VIEW = "django.views.csrf.csrf_failure"

    # Trusted origins (HTTP + ports)
    CSRF_TRUSTED_ORIGINS += [
        "http://127.0.0.1:8000", "http://127.0.0.1:8001",
        "http://localhost:8000", "http://localhost:8001",
        "http://localhost:3000", "http://127.0.0.1:3000",
    ]

else:
    # Prod: enforce HTTPS and strong headers
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
    SECURE_CROSS_ORIGIN_EMBEDDER_POLICY = "require-corp"

    # Cookies & CSRF
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True  # set to False if JS needs to read it


# ────────────────────────────────────────────────────
# Email
# ────────────────────────────────────────────────────
EMAIL_BACKEND = ENV("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
DEFAULT_FROM_EMAIL = ENV("DEFAULT_FROM_EMAIL", "noreply@ourfinancetracker.com")
EMAIL_LINK_DOMAIN = ENV("EMAIL_LINK_DOMAIN", "www.ourfinancetracker.com")
EMAIL_HOST = ENV("EMAIL_HOST", "")
EMAIL_PORT = int(ENV("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", "true")
EMAIL_HOST_USER = ENV("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = ENV("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = int(ENV("EMAIL_TIMEOUT", "20"))
SERVER_EMAIL = ENV("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
if DEBUG and not EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ────────────────────────────────────────────────────
# django-axes (brute-force)
# ────────────────────────────────────────────────────
AXES_ENABLED = not DEBUG
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
AXES_LOCKOUT_CALLABLE = None

# ────────────────────────────────────────────────────
# Logging (simple and sufficient)
# ────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler", "level": "DEBUG"},
        "null": {"class": "logging.NullHandler"},
    },
    "root": {"handlers": ["console"] if DEBUG else ["null"], "level": "DEBUG" if DEBUG else "INFO"},
    "loggers": {
        "django.server": {
            "handlers": ["console"] if DEBUG else ["null"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"] if DEBUG else ["null"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# ────────────────────────────────────────────────────
# Supabase (if needed in code)
# ────────────────────────────────────────────────────
SUPABASE_URL = ENV("SUPABASE_URL")
SUPABASE_KEY = ENV("SUPABASE_KEY")
SUPABASE_JWT_SECRET = ENV("SUPABASE_JWT_SECRET")

# Celery
CELERY_BROKER_URL = ENV("CELERY_BROKER_URL", default="memory://")
CELERY_RESULT_BACKEND = ENV("CELERY_RESULT_BACKEND", default="cache+memory://")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# --- Final dev overrides (must stay at the end of settings.py) ---
if DEBUG:
    # Do not force HTTPS in dev
    SECURE_SSL_REDIRECT = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False

    # Do not emit the CSP upgrade directive in dev
    CONTENT_SECURITY_POLICY["DIRECTIVES"].pop("upgrade-insecure-requests", None)

    # No HSTS while on HTTP
    SECURE_HSTS_SECONDS = 0
