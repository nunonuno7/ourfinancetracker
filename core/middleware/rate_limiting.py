
import time
from collections import defaultdict, deque
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache

class RateLimitMiddleware(MiddlewareMixin):
    """Rate limiting básico por IP e utilizador"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limits = {
            'api': {'requests': 100, 'window': 3600},  # 100 req/hora para APIs
            'transactions': {'requests': 50, 'window': 300},  # 50 req/5min para transações
        }
    
    def process_request(self, request):
        # Determinar tipo de endpoint
        endpoint_type = self.get_endpoint_type(request.path)
        if not endpoint_type:
            return None
        
        # Obter identificador (IP ou user)
        identifier = self.get_identifier(request)
        if not identifier:
            return None
        
        # Verificar rate limit
        if self.is_rate_limited(identifier, endpoint_type):
            return JsonResponse(
                {'error': 'Rate limit exceeded. Please try again later.'},
                status=429
            )
        
        return None
    
    def get_endpoint_type(self, path):
        """Determina o tipo de endpoint baseado no path"""
        if '/transactions/json' in path:
            return 'transactions'
        elif path.startswith('/api/'):
            return 'api'
        return None
    
    def get_identifier(self, request):
        """Obtém identificador único para rate limiting"""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"user:{request.user.id}"
        return f"ip:{self.get_client_ip(request)}"
    
    def get_client_ip(self, request):
        """Obtém IP real do cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')
    
    def is_rate_limited(self, identifier, endpoint_type):
        """Verifica se o utilizador excedeu o rate limit"""
        limits = self.rate_limits.get(endpoint_type, {})
        if not limits:
            return False
        
        cache_key = f"rate_limit:{endpoint_type}:{identifier}"
        current_time = int(time.time())
        window = limits['window']
        max_requests = limits['requests']
        
        # Obter timestamps das requests
        timestamps = cache.get(cache_key, [])
        
        # Remover timestamps antigos
        cutoff_time = current_time - window
        timestamps = [ts for ts in timestamps if ts > cutoff_time]
        
        # Verificar se excede o limite
        if len(timestamps) >= max_requests:
            return True
        
        # Adicionar timestamp atual
        timestamps.append(current_time)
        cache.set(cache_key, timestamps, window + 60)  # Cache por mais tempo que a janela
        
        return False
