import importlib


def test_production_uses_argon2():
    """Ensure production settings use Argon2 for password hashing."""
    settings = importlib.import_module("ourfinancetracker_site.settings")
    assert settings.PASSWORD_HASHERS[0] == "django.contrib.auth.hashers.Argon2PasswordHasher"


def test_production_uses_django_axes():
    """Ensure production settings enable django-axes for login lockouts."""
    settings = importlib.import_module("ourfinancetracker_site.settings")
    assert "axes" in settings.INSTALLED_APPS
    assert settings.MIDDLEWARE[-1] == "axes.middleware.AxesMiddleware"
    assert settings.AUTHENTICATION_BACKENDS[0] == "axes.backends.AxesStandaloneBackend"
    assert settings.AXES_FAILURE_LIMIT == 5
