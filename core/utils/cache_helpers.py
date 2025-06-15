from django.core.cache import cache

def clear_tx_cache(user_id: int) -> None:
    prefix = f"tx_cache_user_{user_id}_"
    prefix_colon = f":1:{prefix}"

    deleted = 0
    backend = getattr(cache, "__class__", None).__name__
    print(f"🧠 Tipo de backend de cache: {backend}")

    try:
        client = cache.client.get_client()
        keys = client.keys(f"{prefix}*")
        if keys:
            client.delete(*keys)
            print(f"🧹 Redis: {len(keys)} entradas apagadas via client.delete")
            return
    except Exception as e:
        print(f"⚠️ Falha ao limpar via Redis: {e}")

    # Fallback LocMemCache
    try:
        internal_cache = getattr(cache, "_cache", {})
        for key in list(internal_cache.keys()):
            key_str = key.decode() if isinstance(key, bytes) else str(key)
            if key_str.startswith(prefix) or key_str.startswith(prefix_colon):
                cache.delete(key_str)  # ⬅️ aqui está a solução real!
                deleted += 1
                print(f"🗑️ Removido com cache.delete(): {key_str}")
        print(f"🧹 {deleted} entradas apagadas com cache.delete() (LocMemCache) para user_id={user_id}")
    except Exception as e:
        print(f"❌ Falha ao limpar LocMemCache: {e}")
