"""
Cache utilities para o ourfinancetracker.
Funções para gerir cache de transações de forma segura e eficiente.
"""
import hashlib
from typing import Optional
from django.core.cache import cache
from django.conf import settings


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
    # Construir chave completa
    if key_prefix:
        full_key = f"{key_prefix}:{key}"
    else:
        full_key = key
        
    if version is not None:
        full_key = f"{full_key}:v{version}"
    
    # Hash da SECRET_KEY para segurança (primeiros 8 caracteres)
    secret_hash = hashlib.md5(settings.SECRET_KEY.encode()).hexdigest()[:8]
    full_key = f"{full_key}:{secret_hash}"
    
    # Garantir que a chave é segura para memcached (< 250 chars, sem espaços)
    if len(full_key) > 240 or ' ' in full_key:
        # Hash da chave se for muito longa ou contém espaços
        hashed = hashlib.md5(full_key.encode()).hexdigest()
        return f"hashed:{hashed}"
    
    return full_key


def clear_tx_cache(user_id: int) -> None:
    """
    Limpa todas as chaves de cache relacionadas com transações de um utilizador.
    
    Args:
        user_id: ID do utilizador cujo cache deve ser limpo
    """
    try:
        # Padrões de chaves que precisam ser limpas
        patterns = [
            f"tx_cache_user_{user_id}_*",
            f"account_balance_user_{user_id}_*", 
            f"category_cache_user_{user_id}_*",
        ]
        
        # Nota: Esta é uma implementação simplificada
        # Para production com Redis, seria melhor usar SCAN com padrões
        cache.clear()  # Alternativa segura mas menos eficiente
        
    except Exception as e:
        # Log do erro mas não falha a operação principal
        print(f"Erro ao limpar cache: {e}")


def get_cache_key_for_transactions(user_id: int, start_date: str, end_date: str) -> str:
    """
    Gera chave de cache específica para transações de um utilizador num período.
    
    Args:
        user_id: ID do utilizador
        start_date: Data de início (formato string)
        end_date: Data de fim (formato string)
        
    Returns:
        Chave de cache segura
    """
    base_key = f"tx_cache_user_{user_id}_{start_date}_{end_date}"
    return make_key(base_key, key_prefix="ourfinance")
