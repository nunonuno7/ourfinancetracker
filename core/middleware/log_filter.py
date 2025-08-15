"""Request-aware logging suppression middleware."""

import logging
import threading


_thread_local = threading.local()


class _NoisyPathFilter(logging.Filter):
    """Filter that hides low-level logs for noisy endpoints."""

    noisy_paths = ('/transactions/json', '/api/', '/dashboard/kpis')

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - small utility
        path = getattr(_thread_local, "path", "")
        if any(p in path for p in self.noisy_paths):
            return record.levelno >= logging.WARNING
        return True


class SuppressJsonLogMiddleware:
    """Suppress noisy logs for JSON/reporting endpoints."""

    def __init__(self, get_response):
        self.get_response = get_response
        logging.getLogger("django.server").addFilter(_NoisyPathFilter())

    def __call__(self, request):
        _thread_local.path = request.path
        try:
            return self.get_response(request)
        finally:
            try:
                del _thread_local.path
            except AttributeError:  # pragma: no cover - safety
                pass

