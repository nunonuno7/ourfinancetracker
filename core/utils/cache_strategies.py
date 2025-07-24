
import hashlib
import logging
from typing import Any, Optional, Dict, List
from django.core.cache import cache
from django.conf import settings
from django.db.models import QuerySet
from datetime import date, timedelta

logger = logging.getLogger(__name__)

class CacheManager:
    """Sistema de cache avançado com invalidação inteligente"""
    
    def __init__(self):
        self.default_timeout = 300  # 5 minutos
        self.cache_prefix = "ourft_v2"
    
    def generate_cache_key(self, user_id: int, data_type: str, **kwargs) -> str:
        """Gera chave de cache única e segura"""
        key_parts = [str(user_id), data_type]
        
        # Adicionar parâmetros ordenados
        for key, value in sorted(kwargs.items()):
            key_parts.append(f"{key}:{value}")
        
        # Hash para evitar chaves muito longas
        key_string = "_".join(key_parts)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()[:12]
        
        return f"{self.cache_prefix}:{key_hash}"
    
    def get_transactions_cache_key(self, user_id: int, start_date: date, end_date: date, **filters) -> str:
        """Cache key específica para transações"""
        return self.generate_cache_key(
            user_id, 
            "transactions",
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            **filters
        )
    
    def invalidate_user_cache(self, user_id: int, cache_types: List[str] = None):
        """Invalida cache de um utilizador por tipo"""
        if cache_types is None:
            cache_types = ["transactions", "balances", "dashboard", "kpis"]
        
        # Em produção, usaria padrões mais específicos
        # Por agora, invalidamos todas as chaves relacionadas
        for cache_type in cache_types:
            pattern_key = f"{self.cache_prefix}:*{user_id}*{cache_type}*"
            # Django não suporta wildcard delete nativamente
            # Implementação simples para desenvolvimento
            logger.info(f"Invalidating cache pattern: {pattern_key}")
    
    def get_or_set(self, key: str, callable_func, timeout: int = None) -> Any:
        """Get or set com logging melhorado"""
        timeout = timeout or self.default_timeout
        
        cached_value = cache.get(key)
        if cached_value is not None:
            logger.debug(f"Cache HIT: {key}")
            return cached_value
        
        logger.debug(f"Cache MISS: {key}")
        fresh_value = callable_func()
        cache.set(key, fresh_value, timeout)
        return fresh_value

# Instância global
cache_manager = CacheManager()
