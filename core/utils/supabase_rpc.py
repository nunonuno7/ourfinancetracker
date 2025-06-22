import os
import requests
import json
from django.core.exceptions import ImproperlyConfigured
from .supabase_jwt import generate_supabase_jwt
import logging

logger = logging.getLogger(__name__)


def get_env_or_fail(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ImproperlyConfigured(f"A variável de ambiente '{key}' está em falta.")
    return value


def call_rpc(user_id: int, fn_name: str, payload: dict | None = None) -> dict:
    try:
        rest_url = get_env_or_fail("SUPABASE_REST_URL")
        api_key = get_env_or_fail("SUPABASE_API_KEY")
    except ImproperlyConfigured as e:
        logger.error(f"❌ Configuração inválida: {e}")
        raise

    token = generate_supabase_jwt(user_id=user_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    url = f"{rest_url}/rpc/{fn_name}"
    logger.info(f"🔗 Chamada RPC para {url}")
    logger.debug(f"📦 Payload: {json.dumps(payload or {}, indent=2)}")

    try:
        resp = requests.post(url, headers=headers, json=payload or {})
        resp.raise_for_status()
        logger.info(f"✅ Resposta Supabase: {resp.status_code}")
        return resp.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"❌ Erro HTTP {resp.status_code}: {resp.text}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Erro de rede: {e}")
        raise
