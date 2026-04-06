"""
Cache utilities for ourfinancetracker.
Helpers for managing transaction cache safely and efficiently.
"""

import hashlib
import logging
from contextlib import contextmanager
from fnmatch import fnmatch
from typing import Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


@contextmanager
def bulk_operation():
    """
    Context manager for bulk operations that temporarily disables automatic
    cache clearing.
    """
    # Mark that a bulk operation is currently running
    bulk_operation._active = True
    try:
        yield
    finally:
        # Remove the flag when leaving the context
        if hasattr(bulk_operation, "_active"):
            delattr(bulk_operation, "_active")


def is_bulk_operation_active():
    """Return whether a bulk operation is currently active."""
    return hasattr(bulk_operation, "_active")


def make_key(key: str, key_prefix: str = "", version: Optional[int] = None) -> str:
    """
    Build a safe and consistent cache key.

    Args:
        key: The base key
        key_prefix: Optional key prefix
        version: Optional key version

    Returns:
        A processed cache-safe key string
    """
    full_key = f"{key_prefix}:{key}" if key_prefix else key
    if version is not None:
        full_key = f"{full_key}:v{version}"

    # Add a SECRET_KEY hash for cross-project isolation
    secret_hash = hashlib.sha256(settings.SECRET_KEY.encode()).hexdigest()[:10]
    full_key = f"{full_key}:{secret_hash}"

    # Ensure the final key does not exceed limits or contain spaces
    if len(full_key) > 240 or " " in full_key:
        hashed = hashlib.sha256(full_key.encode()).hexdigest()
        return f"hashed:{hashed}"

    return full_key


def clear_tx_cache(user_id: int, force: bool = False) -> None:
    """
    Clear all cache keys related to a user's transactions.
    Optimized to avoid excessive invalidation.

    Args:
        user_id: User ID
        force: When ``True``, skip throttling and always clear the cache.
    """
    # Throttle cache clearing to once per minute per user unless forced
    throttle_key = f"cache_clear_throttle_{user_id}"
    if not force and cache.get(throttle_key):
        logger.debug(f"Cache clearing throttled for user {user_id}")
        return

    logger.info(f"Clearing transaction cache for user_id={user_id}")
    cache.set(throttle_key, True, timeout=60)  # 1 minute

    # Hash the SECRET_KEY to avoid collisions across environments
    secret_hash = hashlib.sha256(settings.SECRET_KEY.encode()).hexdigest()[:10]

    # Cache patterns to clear
    cache_patterns = [
        f"tx_cache_user_{user_id}_*",
        f"tx_v2_{user_id}_*",
        f"ourfinance:account_balance_user_{user_id}_*:{secret_hash}",
        f"ourfinance:category_cache_user_{user_id}_*:{secret_hash}",
    ]

    for pattern in cache_patterns:
        logger.debug(f"Clearing cache key pattern: {pattern}")

        # Use Redis pattern matching when available
        try:
            from django.core.cache.backends.redis import RedisCache

            if isinstance(cache, RedisCache):
                # Redis supports wildcard matching
                keys = cache._cache.get_client().keys(pattern)
                if keys:
                    cache._cache.get_client().delete(*keys)
            elif _clear_locmem_cache_keys(pattern):
                continue
            else:
                # Fallback for other backends - clear specific keys
                _clear_specific_cache_keys(user_id, secret_hash)
        except ImportError:
            # Fallback when Redis is not available
            if not _clear_locmem_cache_keys(pattern):
                _clear_specific_cache_keys(user_id, secret_hash)


def _clear_locmem_cache_keys(pattern: str) -> bool:
    """
    Clear cache entries by wildcard pattern for backends that expose an
    in-memory key dictionary (e.g. LocMemCache used in tests/dev).
    """
    backend_cache = getattr(cache, "_cache", None)
    if backend_cache is None or not hasattr(backend_cache, "keys"):
        return False

    matched = False
    # LocMemCache stores keys as ':<version>:<key>'
    for stored_key in list(backend_cache.keys()):
        original_key = stored_key.split(":", 2)[-1]
        if fnmatch(original_key, pattern):
            cache.delete(original_key)
            matched = True

    return matched


def _clear_specific_cache_keys(user_id: int, secret_hash: str) -> None:
    """
    Clear specific cache keys when Redis is not available.

    Args:
        user_id: User ID
        secret_hash: Hash derived from ``SECRET_KEY`` for related keys.
    """
    # List of specific keys to clear
    cache_keys_to_clear = []

    # Generate keys for the last 12 months
    from datetime import date, timedelta

    today = date.today()

    for i in range(12):
        month_date = today - timedelta(days=i * 30)
        start_date = month_date.replace(day=1)
        end_date = month_date

        # Transaction keys use a dedicated hash with SECRET_KEY + user + dates
        raw = f"{settings.SECRET_KEY}:{user_id}:{start_date}:{end_date}".encode()
        digest = hashlib.sha256(raw).hexdigest()
        tx_key = f"tx_cache_user_{user_id}_{start_date}_{end_date}_{digest}"
        cache_keys_to_clear.append(tx_key)

        # API v2 keys (no hash, but include sorting)
        for sort_field in ["date", "amount", "type"]:
            for sort_dir in ["asc", "desc"]:
                tx_v2_key = (
                    f"tx_v2_{user_id}_{start_date}_{end_date}_{sort_field}_{sort_dir}"
                )
                cache_keys_to_clear.append(tx_v2_key)

        # Balance keys
        balance_key = (
            f"ourfinance:account_balance_user_{user_id}_{start_date}:{secret_hash}"
        )
        cache_keys_to_clear.append(balance_key)

        # Category keys
        category_key = (
            f"ourfinance:category_cache_user_{user_id}_{start_date}:{secret_hash}"
        )
        cache_keys_to_clear.append(category_key)

    # Clear every collected key
    for key in cache_keys_to_clear:
        try:
            cache.delete(key)
        except Exception:
            pass  # Ignore individual delete failures


def get_cache_key_for_transactions(user_id: int, start_date, end_date) -> str:
    """
    Generate a cache key for a user's transactions within a date range.

    Args:
        user_id: User ID
        start_date: Start date or ISO-like string
        end_date: End date or ISO-like string

    Returns:
        Safe cache key
    """
    raw = f"{settings.SECRET_KEY}:{user_id}:{start_date}:{end_date}".encode()
    digest = hashlib.sha256(raw).hexdigest()
    return f"tx_cache_user_{user_id}_{start_date}_{end_date}_{digest}"
