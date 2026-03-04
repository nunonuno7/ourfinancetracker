import hashlib
import secrets
from django.core.cache import cache
from django.conf import settings


def _cache_key(user_id: int) -> str:
    return f"activation:{user_id}"


def generate_activation_token(user) -> str:
    """Generate a secure activation token for ``user`` and store its hash."""
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    timeout = int(getattr(settings, "ACCOUNT_ACTIVATION_TOKEN_EXPIRATION_SECONDS", 900))
    cache.set(_cache_key(user.pk), token_hash, timeout)
    return token


def validate_activation_token(user, token: str) -> bool:
    """Check whether ``token`` matches the stored hash for ``user``."""
    token_hash = cache.get(_cache_key(user.pk))
    if not token_hash:
        return False
    candidate = hashlib.sha256(token.encode()).hexdigest()
    return secrets.compare_digest(token_hash, candidate)


def revoke_activation_token(user) -> None:
    """Manually revoke ``user``'s activation token."""
    cache.delete(_cache_key(user.pk))
