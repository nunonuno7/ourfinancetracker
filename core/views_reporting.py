import os
import jwt
import requests
from datetime import datetime, timedelta
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.http import require_GET
from django.core.exceptions import ImproperlyConfigured

import logging
logger = logging.getLogger(__name__)


def get_env_or_fail(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ImproperlyConfigured(f"A variável de ambiente '{key}' está em falta.")
    return value


@require_GET
def proxy_report_csv_token(request):
    """
    Endpoint público que aceita um token JWT no URL:
    /reporting/data.csv?token=...

    Este token deve conter o 'sub' com o user_id.
    """
    token = request.GET.get("token", "")
    if not token:
        logger.warning("❌ Token em falta")
        return HttpResponseForbidden("❌ Token em falta.")

    try:
        service_role_key = get_env_or_fail("SUPABASE_SERVICE_ROLE_KEY")
        decoded = jwt.decode(token, service_role_key, algorithms=["HS256"])
        logger.info(f"✅ Token original decodificado: {decoded}")

        user_id = decoded.get("sub")
        if not user_id:
            logger.warning("❌ JWT inválido – 'sub' ausente")
            return HttpResponseForbidden("❌ JWT inválido – sub ausente.")

    except jwt.ExpiredSignatureError:
        logger.warning("❌ Token expirado")
        return HttpResponseForbidden("❌ Token expirado.")
    except jwt.InvalidTokenError as e:
        logger.warning(f"❌ Token inválido: {e}")
        return HttpResponseForbidden("❌ Token inválido.")
    except ImproperlyConfigured as e:
        logger.error(f"❌ Configuração inválida: {e}")
        return HttpResponse(str(e), status=500)

    # Gerar novo JWT curto (5 min) com o mesmo sub
    fresh_payload = {
        "sub": str(user_id),
        "user_id": int(user_id),
        "role": "authenticated",
        "exp": datetime.utcnow() + timedelta(minutes=5)
    }
    fresh_token = jwt.encode(fresh_payload, service_role_key, algorithm="HS256")
    logger.info(f"🔐 Novo JWT gerado para Supabase: {fresh_token}")
    logger.debug(f"🧾 Payload JWT novo: {fresh_payload}")

    try:
        api_key = get_env_or_fail("SUPABASE_API_KEY")
        rest_url = get_env_or_fail("SUPABASE_REST_URL")
    except ImproperlyConfigured as e:
        logger.error(f"❌ Configuração inválida: {e}")
        return HttpResponse(str(e), status=500)

    headers = {
        "Authorization": f"Bearer {fresh_token}",
        "apikey": api_key,
        "Accept": "text/csv"
    }
    logger.debug(f"🔗 Headers enviados para Supabase: {headers}")

    url = f"{rest_url}/reporting_transactions?select=date,amount,type,category,account,notes"
    logger.debug(f"🔗 URL chamada: {url}")

    r = requests.get(url, headers=headers)
    logger.info(f"📥 Resposta Supabase: status={r.status_code}")
    if r.status_code != 200:
        logger.warning(f"❌ Conteúdo da resposta: {r.text}")
        return HttpResponse(f"❌ Erro Supabase: {r.status_code}", status=r.status_code)

    response = HttpResponse(r.content, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename=reporting.csv'
    return response
