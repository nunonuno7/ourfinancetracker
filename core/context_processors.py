from django.conf import settings


def sentry_dsn(request):
    """Expose SENTRY_DSN so templates can initialize Sentry browser SDK."""
    return {"SENTRY_DSN": getattr(settings, "SENTRY_DSN", "")}
