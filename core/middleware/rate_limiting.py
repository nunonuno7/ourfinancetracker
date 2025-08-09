import time
from django.http import JsonResponse
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin

class RateLimitMiddleware(MiddlewareMixin):
    """Rate limiting for heavy API endpoints"""

    RATE_LIMITS = {
        '/transactions/totals-v2/': {'requests': 30, 'window': 60},  # 30 requests per minute
        '/dashboard/kpis/': {'requests': 20, 'window': 60},          # 20 requests per minute
        '/transactions/json': {'requests': 50, 'window': 60},        # 50 requests per minute
    }

    def process_request(self, request):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None

        path = request.path

        # Check if this path needs rate limiting
        for limited_path, limits in self.RATE_LIMITS.items():
            if limited_path in path:
                cache_key = f"rate_limit:{request.user.id}:{limited_path}"
                current_time = int(time.time())
                window_start = current_time - limits['window']

                # Get current request timestamps
                requests = cache.get(cache_key, [])

                # Filter out old requests
                requests = [req_time for req_time in requests if req_time > window_start]

                # Check if limit exceeded
                if len(requests) >= limits['requests']:
                    return JsonResponse({
                        'error': 'Rate limit exceeded',
                        'detail': f"Maximum {limits['requests']} requests per {limits['window']} seconds"
                    }, status=429)

                # Add current request
                requests.append(current_time)
                cache.set(cache_key, requests, limits['window'])

        return None