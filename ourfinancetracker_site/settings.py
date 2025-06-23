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
SECRET_KEY, DEBUG, DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT (5432),
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
# Segurança & chave secreta
# ────────────────────────────────────────────────────
DEBUG: bool = ENV("DEBUG", "False").lower() in {"1", "true", "yes", "on"}
SECRET_KEY: str | None = ENV("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required")

# ────────────────────────────────────────────────────
# Hosts e CSRF
# ────────────────────────────────────────────────────
ALLOWED_HOSTS: List[str] = [
    "ourfinancetracker.onrender.com",
    "ourfinancetracker.com",
    "www.ourfinancetracker.com",
    "localhost",
    "127.0.0.1",
]
if ext_host := ENV("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(ext_host)
if DEBUG:
    # Em desenvolvimento, permite qualquer host (incluindo Replit)
    ALLOWED_HOSTS = ["*"]

CSRF_TRUSTED_ORIGINS: List[str] = [
    "https://ourfinancetracker.onrender.com",
    "https://ourfinancetracker.com",
]
if DEBUG:
    # Adiciona o hostname específico do Replit
    CSRF_TRUSTED_ORIGINS.append(
        "https://4ba2dbda-5496-4779-9376-d32db8a6f52b-00-13hxb2otssmz5.worf.replit.dev"
    )
    # Mantém o ngrok para desenvolvimento local
    CSRF_TRUSTED_ORIGINS.append(
        "https://4aa6-2001-818-c407-a00-2d64-ff89-1771-c9e.ngrok-free.app"
    )
    # Adiciona localhost para desenvolvimento local
    CSRF_TRUSTED_ORIGINS.extend([
        "http://127.0.0.1:8000",
        "http://localhost:8000"
    ])

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
    # Terceiros
    "whitenoise.runserver_nostatic",
    "widget_tweaks",
    "django.contrib.humanize",
    # Internos
    "core",
]
if DEBUG:
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
]
if DEBUG:
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
        "DIRS": [BASE_DIR / "core" / "templates"],
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
STATICFILES_STORAGE = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage" if not DEBUG else "django.contrib.staticfiles.storage.StaticFilesStorage"
)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ────────────────────────────────────────────────────
# Autenticação
# ────────────────────────────────────────────────────
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ────────────────────────────────────────────────────
# Logging estruturado
# ────────────────────────────────────────────────────
class SuppressTransactionJsonFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        return "/transactions/json" not in record.getMessage()

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"suppress_transaction_json": {"()": SuppressTransactionJsonFilter}},
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {"format": "[{levelname}] {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple" if DEBUG else "verbose",
            "filters": ["suppress_transaction_json"],
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "django.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "DEBUG" if DEBUG else "INFO",
    },
    "loggers": {
        "django.server": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "core": {"handlers": ["console", "file"], "level": "DEBUG" if DEBUG else "INFO", "propagate": False},
    },
}

# ────────────────────────────────────────────────────
# Segurança extra
# ────────────────────────────────────────────────────
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = "DENY"
else:
    # Configurações para desenvolvimento local
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# ────────────────────────────────────────────────────
# Supabase creds (para RPC)
# ────────────────────────────────────────────────────
SUPABASE_URL = ENV("SUPABASE_URL")
SUPABASE_KEY = ENV("SUPABASE_KEY")
SUPABASE_JWT_SECRET = ENV("SUPABASE_JWT_SECRET")
