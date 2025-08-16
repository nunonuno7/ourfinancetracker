"""Simple rate limiting middleware for selected endpoints."""

from django.http import JsonResponse
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin


class RateLimitMiddleware(MiddlewareMixin):
    """Apply per-user/IP rate limits on selected paths."""

    RATE_LIMITS = {
        '/transactions/totals-v2/': {"requests": 30, "window": 60, "scope": "user"},
        '/dashboard/kpis/': {"requests": 20, "window": 60, "scope": "user"},
        '/transactions/json': {"requests": 50, "window": 60, "scope": "user"},
        '/accounts/login/': {"requests": 5, "window": 60, "scope": "ip+username"},
        '/accounts/signup/': {"requests": 5, "window": 60, "scope": "ip"},
    }

    @staticmethod
    def _get_client_ip(request):
        """Return best-effort client IP."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')

    def process_request(self, request):  # noqa: C901 - small middleware
        path = request.path

        for limited_path, limits in self.RATE_LIMITS.items():
            if path != limited_path:
                continue

            scope = limits.get('scope', 'user')
            identifier = None
            if scope == 'user':
                if not getattr(request, 'user', None) or not request.user.is_authenticated:
                    return None
                identifier = request.user.id
            elif scope == 'ip':
                identifier = self._get_client_ip(request)
            elif scope == 'ip+username':
                identifier = f"{self._get_client_ip(request)}:{request.POST.get('username', '')}"

            if not identifier:
                return None

            cache_key = f"rate_limit:{identifier}:{limited_path}"
            # Initialize key with timeout if absent, then increment atomically
            cache.add(cache_key, 0, limits['window'])
            count = cache.incr(cache_key)
            if count > limits['requests']:
                return JsonResponse({'detail': 'Too many requests'}, status=429)
            break

        return None
