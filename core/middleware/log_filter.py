class SuppressJsonLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/transactions/json"):
            response._suppress_logging = True
        return response
import logging

class SuppressJsonLogMiddleware:
    """Middleware to suppress noisy JSON endpoint logs."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Suppress logs for specific endpoints
        if any(path in request.path for path in ['/transactions/json', '/api/', '/dashboard/kpis']):
            # Temporarily increase log level
            logger = logging.getLogger('django.server')
            old_level = logger.level
            logger.setLevel(logging.WARNING)
            
            response = self.get_response(request)
            
            # Restore log level
            logger.setLevel(old_level)
            return response
        
        return self.get_response(request)
