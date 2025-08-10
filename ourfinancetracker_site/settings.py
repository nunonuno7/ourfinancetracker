"""Django **settings.py** — versão optimizada para **Supabase Postgres**.

Principais características 🔧
────────────────────────────
• Mantém‐se compatível com desenvolvimento local *(SQLite)* caso o
  Postgres não esteja configurado, mas **usa sempre a mesma base Supabase**
  quando presentes as variáveis DB_* ou DATABASE_URL.
• Carrega variáveis de ambiente via **python‑dotenv**.
• Debug Toolbar apenas em `DEBUG=True`.
• Redis opcional — se `REDIS_URL` não existir recorre a `LocMemCache`.
• WhiteNoise para servir estáticos em produção.
• Logging com **RotatingFileHandler** e filtro para suprimir spam das
  chamadas JSON.

EnvVars mínimas ⬇️
─────────────────
SECRET_KEY, DEBUG, DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT (5432),
REDIS_URL *(opcional)*, SUPABASE_URL, SUPABASE_KEY, SUPABASE_JWT_SECRET.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

try:
    import dj_database_url  # type: ignore
except ImportError:  # pragma: no cover
    dj_database_url = None

# ────────────────────────────────────────────────────
# Carregar .env (se existir)
# ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

ENV = os.getenv  # alias

# ────────────────────────────────────────────────────
# Authentication backends (django-axes must be first)
# ────────────────────────────────────────────────────
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
    # add others here if you use them (e.g. allauth)
]

# ────────────────────────────────────────────────────
# Segurança & chave secreta
# ────────────────────────────────────────────────────
DEBUG: bool = ENV("DEBUG", "False").lower() in {"1", "true", "yes", "on"}
SECRET_KEY: str | None = ENV("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required")

# ────────────────────────────────────────────────────
# Hosts e CSRF
# ────────────────────────────────────────────────────
# Hosts allowed to serve the app (no scheme here)
ALLOWED_HOSTS = [
    ".ourfinancetracker.com",   # both ourfinancetracker.com and subdomains
    ".onrender.com",            # Render
    ".replit.dev",              # Replit
    "localhost",
    "127.0.0.1",
]

# CSRF trusted origins (must include scheme; ports allowed for non-standard ports)
CSRF_TRUSTED_ORIGINS = [
    "https://ourfinancetracker.com",
    "https://www.ourfinancetracker.com",
    "https://*.onrender.com",
    "https://*.replit.dev",
    "https://*.replit.dev:3000",
    "https://*.replit.dev:5000",
    "http://localhost:8000",
    "http://localhost:8001",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8001",
]

def _extend_from_env_list(env_key, target_list, require_scheme=False):
    raw = os.getenv(env_key, "")
    if not raw:
        return
    for item in [x.strip() for x in raw.split(",") if x.strip()]:
        if require_scheme and not (item.startswith("http://") or item.startswith("https://")):
            # Skip invalid origin if scheme is missing
            continue
        target_list.append(item)

_extend_from_env_list("EXTRA_ALLOWED_HOSTS", ALLOWED_HOSTS, require_scheme=False)
_extend_from_env_list("EXTRA_CSRF_TRUSTED_ORIGINS", CSRF_TRUSTED_ORIGINS, require_scheme=True)

# Adicionar configuração específica para CSRF em desenvolvimento
if DEBUG:
    CSRF_COOKIE_SAMESITE = 'Lax'
    CSRF_USE_SESSIONS = False
    CSRF_COOKIE_HTTPONLY = False
    # Para debug CSRF em desenvolvimento
    CSRF_FAILURE_VIEW = 'django.views.csrf.csrf_failure'

# ────────────────────────────────────────────────────
# Apps & middleware
# ────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Terceiros
    "whitenoise.runserver_nostatic",
    "widget_tweaks",
    "django.contrib.humanize",
    "axes",
    "anymail",
    # Internos
    "accounts",  # Moved before core to prioritize its templates
    "core",
]

# Debug Toolbar only if explicitly toggled
SHOW_DEBUG_TOOLBAR = ENV("SHOW_DEBUG_TOOLBAR", "False").lower() in {"1", "true", "yes", "on"}
if DEBUG and SHOW_DEBUG_TOOLBAR:
    INSTALLED_APPS += ["debug_toolbar"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.log_filter.SuppressJsonLogMiddleware",
    # Performance monitoring (only in DEBUG)
    "core.middleware.performance.PerformanceMiddleware" if DEBUG else None,
    # django-axes should be last
    "axes.middleware.AxesMiddleware",
]

# Remove None values from middleware list
MIDDLEWARE = [m for m in MIDDLEWARE if m is not None]

# Add Debug Toolbar middleware if enabled
if DEBUG and SHOW_DEBUG_TOOLBAR:
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
    INTERNAL_IPS = ["127.0.0.1"]

ROOT_URLCONF = "ourfinancetracker_site.urls"
WSGI_APPLICATION = "ourfinancetracker_site.wsgi.application"

# ────────────────────────────────────────────────────
# Templates
# ────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "accounts" / "templates",
            BASE_DIR / "core" / "templates"
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

# ────────────────────────────────────────────────────
# Base de dados – prioriza Supabase/Postgres
# ────────────────────────────────────────────────────
SUPA_URL = ENV("DATABASE_URL")  # string completa
if not SUPA_URL and ENV("DB_HOST"):
    SUPA_URL = (
        f"postgresql://{ENV('DB_USER')}:{ENV('DB_PASSWORD')}@{ENV('DB_HOST')}:"
        f"{ENV('DB_PORT', '5432')}/{ENV('DB_NAME')}"
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
    # Fallback leve para dev — SQLite
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ────────────────────────────────────────────────────
# Cache
# ────────────────────────────────────────────────────
if redis_url := ENV("REDIS_URL"):
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": redis_url,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "KEY_PREFIX": "ourft",
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "ourfinancetracker-cache",
        }
    }

# ────────────────────────────────────────────────────
# Internacionalização
# ────────────────────────────────────────────────────
LANGUAGE_CODE = "en-gb"
TIME_ZONE = ENV("TIME_ZONE", "Europe/Lisbon")
USE_I18N = True
USE_TZ = True

# ────────────────────────────────────────────────────
# Ficheiros estáticos & media
# ────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "core" / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Use WhiteNoise with proper fallback for missing files
if DEBUG:
    STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
else:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Ensure WhiteNoise serves static files with correct MIME types
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = DEBUG

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ────────────────────────────────────────────────────
# Autenticação
# ────────────────────────────────────────────────────
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# Password reset timeout (1 hour = 3600 seconds)
PASSWORD_RESET_TIMEOUT = 3600

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Sites framework
SITE_ID = 1

# ────────────────────────────────────────────────────
# Logging estruturado
# ────────────────────────────────────────────────────
class SuppressNoisyEndpointsFilter(logging.Filter):
    """Suppress logs for noisy API endpoints"""
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        noisy_paths = [
            "/transactions/json",
            "/transactions/totals-v2/",
            "/dashboard/kpis/",
            "/static/",
            "/favicon.ico",
            "/api/",
        ]
        return not any(path in message for path in noisy_paths)

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "suppress_noisy_endpoints": {"()": SuppressNoisyEndpointsFilter},
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
        "require_debug_true": {"()": "django.utils.log.RequireDebugTrue"},
    },
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {"format": "[{levelname}] {message}", "style": "{"},
        "performance": {
            "format": "🚀 [{levelname}] {asctime} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple" if DEBUG else "verbose",
            "filters": ["suppress_noisy_endpoints"],
            "level": "DEBUG" if DEBUG else "INFO",
        },
        "console_noisy": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "level": "WARNING",  # Only warnings and errors for noisy endpoints
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "django.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "level": "INFO",  # File logs start at INFO
        },
        "performance_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "performance.log",
            "maxBytes": 2 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "performance",
            "level": "WARNING",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "DEBUG" if DEBUG else "INFO",
    },
    "loggers": {
        "django.server": {
            "handlers": ["console_noisy", "file"],
            "level": "WARNING",  # Reduce server log noise
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "file"],
            "level": "WARNING",  # Only log request errors
            "propagate": False,
        },
        "core": {
            "handlers": ["console", "file"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "core.performance": {
            "handlers": ["console", "performance_file"],
            "level": "WARNING",  # Only log slow requests
            "propagate": False,
        },
        "accounts": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        # Suppress axios/CORS preflight noise
        "django.security.csrf": {
            "handlers": ["file"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

# ────────────────────────────────────────────────────
# Strong password hashing (Argon2 first)
# ────────────────────────────────────────────────────
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

# Relaxed password policy
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 5}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ────────────────────────────────────────────────────
# Segurança extra
# ────────────────────────────────────────────────────
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = "DENY"

    # Safer defaults in production
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    # If behind a proxy/Render/NGINX:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# SameSite cookies (safe default for both envs)
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# ────────────────────────────────────────────────────
# Login attempt throttling (brute-force protection)
# ────────────────────────────────────────────────────
AXES_ENABLED = not DEBUG
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
AXES_LOCKOUT_CALLABLE = None

# ────────────────────────────────────────────────────
# Email configuration
# ────────────────────────────────────────────────────
# --- Email configuration ---
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@ourfinancetracker.com")
EMAIL_LINK_DOMAIN = os.getenv("EMAIL_LINK_DOMAIN", "www.ourfinancetracker.com")

EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = (os.getenv("EMAIL_USE_TLS", "true").lower() == "true")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "20"))

# In development, default to console backend so emails are visible in the terminal.
if DEBUG and not os.getenv("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Security for cookies (HTTPS in production)
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

# Server email for Django system messages (error reports, etc.)
SERVER_EMAIL = os.getenv("SERVER_EMAIL", os.getenv("DEFAULT_FROM_EMAIL", "noreply@ourfinancetracker.com"))

# ────────────────────────────────────────────────────
# Supabase creds (para RPC)
# ────────────────────────────────────────────────────
SUPABASE_URL = ENV("SUPABASE_URL")
SUPABASE_KEY = ENV("SUPABASE_KEY")
SUPABASE_JWT_SECRET = ENV("SUPABASE_JWT_SECRET")