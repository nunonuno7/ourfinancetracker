"""
Cache utilities para o ourfinancetracker.
Funções para gerir cache de transações de forma segura e eficiente.
"""

import hashlib
import logging
from typing import Optional
from contextlib import contextmanager
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


@contextmanager
def bulk_operation():
    """
    Context manager para operações em bulk que desabilita limpeza automática de cache.
    Use com: with bulk_operation(): ...
    """
    # Marcar que estamos numa operação bulk
    bulk_operation._active = True
    try:
        yield
    finally:
        # Limpar flag quando sair do contexto
        if hasattr(bulk_operation, '_active'):
            delattr(bulk_operation, '_active')


def is_bulk_operation_active():
    """Verifica se estamos numa operação bulk ativa."""
    return hasattr(bulk_operation, '_active')


def make_key(key: str, key_prefix: str = "", version: Optional[int] = None) -> str:
    """
    Cria uma chave de cache segura e consistente.

    Args:
        key: A chave base
        key_prefix: Prefixo opcional para a chave
        version: Versão da chave (opcional)

    Returns:
        String da chave processada e segura para cache
    """
    full_key = f"{key_prefix}:{key}" if key_prefix else key
    if version is not None:
        full_key = f"{full_key}:v{version}"

    # Adiciona hash do secret_key para isolamento multi-projeto
    secret_hash = hashlib.sha256(settings.SECRET_KEY.encode()).hexdigest()[:10]
    full_key = f"{full_key}:{secret_hash}"

    # Garante que a chave final não excede limites ou contém espaços
    if len(full_key) > 240 or ' ' in full_key:
        hashed = hashlib.sha256(full_key.encode()).hexdigest()
        return f"hashed:{hashed}"

    return full_key


def clear_tx_cache(user_id: int) -> None:
    """
    Limpa todas as chaves de cache relacionadas com transações do utilizador.
    Optimizado para evitar limpezas excessivas.

    Args:
        user_id: ID do utilizador
    """
    # Throttle: só limpar cache uma vez por minuto por utilizador
    throttle_key = f"cache_clear_throttle_{user_id}"
    if cache.get(throttle_key):
        logger.debug(f"Cache clearing throttled for user {user_id}")
        return

    logger.info(f"A limpar cache de transações para user_id={user_id}")
    cache.set(throttle_key, True, timeout=60)  # 1 minuto

    # Hash da SECRET_KEY para evitar colisões entre ambientes
    secret_hash = hashlib.sha256(settings.SECRET_KEY.encode()).hexdigest()[:10]

    # Patterns de cache a limpar
    cache_patterns = [
        f"tx_cache_user_{user_id}_*",
        f"tx_v2_{user_id}_*",
        f"ourfinance:account_balance_user_{user_id}_*:{secret_hash}",
        f"ourfinance:category_cache_user_{user_id}_*:{secret_hash}",
    ]

    for pattern in cache_patterns:
        logger.debug(f"Cache limpa para key: {pattern}")

        # Usar pattern matching do Redis se disponível
        try:
            from django.core.cache.backends.redis import RedisCache
            if isinstance(cache, RedisCache):
                # Redis suporta pattern matching
                keys = cache._cache.get_client().keys(pattern)
                if keys:
                    cache._cache.get_client().delete(*keys)
            else:
                # Fallback para outros backends - limpar chaves específicas
                _clear_specific_cache_keys(user_id, secret_hash)
        except ImportError:
            # Fallback se Redis não estiver disponível
            _clear_specific_cache_keys(user_id, secret_hash)


def _clear_specific_cache_keys(user_id: int, secret_hash: str) -> None:
    """
    Limpa chaves específicas de cache quando Redis não está disponível.

    Args:
        user_id: ID do utilizador
        secret_hash: Hash derivado da ``SECRET_KEY`` para outras chaves.
    """
    # Lista de chaves específicas a limpar
    cache_keys_to_clear = []

    # Gerar chaves para os últimos 12 meses
    from datetime import date, timedelta
    today = date.today()

    for i in range(12):
        month_date = today - timedelta(days=i*30)
        start_date = month_date.replace(day=1)
        end_date = month_date

        # Chaves de transações usam hash dedicado com SECRET_KEY + user + datas
        raw = f"{settings.SECRET_KEY}:{user_id}:{start_date}:{end_date}".encode()
        digest = hashlib.sha256(raw).hexdigest()
        tx_key = f"tx_cache_user_{user_id}_{start_date}_{end_date}_{digest}"
        cache_keys_to_clear.append(tx_key)

        # Chaves da API v2 (sem hash, com ordenação)
        for sort_field in ["date", "amount", "type"]:
            for sort_dir in ["asc", "desc"]:
                tx_v2_key = (
                    f"tx_v2_{user_id}_{start_date}_{end_date}_{sort_field}_{sort_dir}"
                )
                cache_keys_to_clear.append(tx_v2_key)

        # Chaves de saldos
        balance_key = f"ourfinance:account_balance_user_{user_id}_{start_date}:{secret_hash}"
        cache_keys_to_clear.append(balance_key)

        # Chaves de categorias
        category_key = f"ourfinance:category_cache_user_{user_id}_{start_date}:{secret_hash}"
        cache_keys_to_clear.append(category_key)

    # Limpar todas as chaves
    for key in cache_keys_to_clear:
        try:
            cache.delete(key)
        except Exception:
            pass  # Ignorar erros individuais


def get_cache_key_for_transactions(user_id: int, start_date: str, end_date: str) -> str:
    """
    Gera chave de cache específica para transações de um utilizador num intervalo.

    Args:
        user_id: ID do utilizador
        start_date: Data de início (formato string)
        end_date: Data de fim (formato string)

    Returns:
        Chave de cache segura
    """
    raw = f"{settings.SECRET_KEY}:{user_id}:{start_date}:{end_date}".encode()
    digest = hashlib.sha256(raw).hexdigest()
    return f"tx_cache_user_{user_id}_{start_date}_{end_date}_{digest}"
