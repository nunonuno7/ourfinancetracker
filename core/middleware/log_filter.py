
import logging

class SuppressJsonLogMiddleware:
    """Suppress noisy logs for JSON/reporting endpoints."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        noisy_paths = ('/transactions/json', '/api/', '/dashboard/kpis')
        if any(p in request.path for p in noisy_paths):
            logger = logging.getLogger('django.server')
            old = logger.level
            logger.setLevel(logging.WARNING)
            try:
                return self.get_response(request)
            finally:
                logger.setLevel(old)
        return self.get_response(request)
