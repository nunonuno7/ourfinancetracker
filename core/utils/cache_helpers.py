"""
Cache utilities para o ourfinancetracker.
Funções para gerir cache de transações de forma segura e eficiente.
"""

import hashlib
import logging
from typing import Optional
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


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
    Limpa todas as chaves de cache relacionadas com transações de um utilizador.

    Args:
        user_id: ID do utilizador cujo cache deve ser limpo
    """
    try:
        logger.info(f"A limpar cache de transações para user_id={user_id}")
        keys = [
            get_cache_key_for_transactions(user_id, "*", "*"),
            make_key(f"account_balance_user_{user_id}_*", "ourfinance"),
            make_key(f"category_cache_user_{user_id}_*", "ourfinance"),
        ]

        # Como não há suporte a wildcards no Django cache padrão, usa-se .delete() manual
        for key in keys:
            cache.delete(key)
            logger.debug(f"Cache limpa para key: {key}")

    except Exception as e:
        logger.exception(f"Erro ao limpar cache para user {user_id}: {e}")


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
    base_key = f"tx_cache_user_{user_id}_{start_date}_{end_date}"
    return make_key(base_key, key_prefix="ourfinance")
