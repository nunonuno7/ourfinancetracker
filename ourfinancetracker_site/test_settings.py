from .settings import *          # herda tudo
import sys

# 👉 Força base de dados SQLite em memória durante pytest
if "pytest" in sys.modules:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

# Evita migrações para acelerar
MIGRATION_MODULES = {
    app.split(".")[0]: None
    for app in INSTALLED_APPS
    if app.startswith("core") or app.startswith("django")
}
