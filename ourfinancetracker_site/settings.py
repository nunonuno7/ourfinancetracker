from pathlib import Path
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente de .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Segurança
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required")  # Critico para segurança[1]

DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'  # DEBUG controlado externamente[2]

ALLOWED_HOSTS = [
    'ourfinancetracker.onrender.com', 'localhost', '127.0.0.1',
    'ourfinancetracker.com', 'www.ourfinancetracker.com'
]
if host := os.getenv("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(host)
if DEBUG:
    ALLOWED_HOSTS += ["4c95-2001-818-c407-a00-2d64-ff89-1771-c9e.ngrok-free.app"]  # Dev hosts[3]

CSRF_TRUSTED_ORIGINS = [
    "https://ourfinancetracker.onrender.com",
    "https://ourfinancetracker.com"
]
if DEBUG:
    CSRF_TRUSTED_ORIGINS.append("https://4aa6-2001-818-c407-a00-2d64-ff89-1771-c9e.ngrok-free.app")  # Dev CSRF[4]

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"

# Apps instaladas
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth",
    "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "django.contrib.staticfiles",
    "core", "widget_tweaks", "django.contrib.humanize"
]
if DEBUG:
    INSTALLED_APPS += ["debug_toolbar"]  # Toolbar em ambiente dev[5]

# Middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'core.middleware.log_filter.SuppressJsonLogMiddleware',
]
if DEBUG:
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
    INTERNAL_IPS = ["127.0.0.1"]  # Toolbar IPs permitidos[6]

ROOT_URLCONF = "ourfinancetracker_site.urls"

# Templates
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "core" / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages"
        ]
    }
}]

WSGI_APPLICATION = "ourfinancetracker_site.wsgi.application"

# Base de dados PostgreSQL configurada por ambiente
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "postgres"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT", "5432")
    }
}

# Validação de passwords
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"}
]

# Internacionalização
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Ficheiros estáticos
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "core" / "static"]
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"  # Produção eficiente[7]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Cache (Redis em produção, locmem em DEBUG)
CACHES = {
    "default": {
        "BACKEND": (
            "django.core.cache.backends.redis.RedisCache"
            if not DEBUG else "django.core.cache.backends.locmem.LocMemCache"
        ),
        "LOCATION": (
            os.getenv("REDIS_URL", "redis://127.0.0.1:6379/1")
            if not DEBUG else "ourfinancetracker-cache"
        ),
        "OPTIONS": (
            {"CLIENT_CLASS": "django_redis.client.DefaultClient"}
            if not DEBUG else {}
        ),
        "KEY_PREFIX": "ourft",
        "TIMEOUT": 300
    }
}



# Logging estruturado

import logging

class SuppressTransactionJsonFilter(logging.Filter):
    def filter(self, record):
        return "/transactions/json" not in record.getMessage()


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "suppress_transaction_json": {
            "()": SuppressTransactionJsonFilter,
        },
    },
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name} {process:d} {thread:d} {message}",
            "style": "{"
        },
        "simple": {"format": "[{levelname}] {message}", "style": "{"}
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple" if DEBUG else "verbose",
            "filters": ["suppress_transaction_json"]
        },
        "file": (
            {
                "class": "logging.FileHandler",
                "filename": os.path.join(BASE_DIR, "django.log"),
                "formatter": "verbose"
            } if not DEBUG else {"class": "logging.NullHandler"}
        )
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG" if DEBUG else "INFO"
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"] if not DEBUG else ["console"],
            "level": "INFO", "propagate": False
        },
        "django.server": {  # <--- logger responsável pelos logs HTTP
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False
        },
        "core": {
            "handlers": ["console", "file"] if not DEBUG else ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False
        }
    }
}


# Segurança extra em produção
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = "DENY"  # Mitigação de clickjacking[8]

# Configurações Supabase (opcional)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
