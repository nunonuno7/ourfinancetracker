import os
import jwt
import requests
from datetime import datetime, timedelta
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.http import require_GET

import logging
logger = logging.getLogger(__name__)


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
        decoded = jwt.decode(
            token,
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
            algorithms=["HS256"]
        )
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

    # Gerar novo JWT curto (5 min) com o mesmo sub
    fresh_payload = {
        "sub": str(user_id),
        "user_id": int(user_id),
        "role": "authenticated",
        "exp": datetime.utcnow() + timedelta(minutes=5)
    }
    fresh_token = jwt.encode(
        fresh_payload,
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        algorithm="HS256"
    )
    logger.info(f"🔐 Novo JWT gerado para Supabase: {fresh_token}")
    logger.debug(f"🧾 Payload JWT novo: {fresh_payload}")

    headers = {
        "Authorization": f"Bearer {fresh_token}",
        "apikey": os.environ["SUPABASE_API_KEY"],
        "Accept": "text/csv"
    }
    logger.debug(f"🔗 Headers enviados para Supabase: {headers}")

    url = f"{os.environ['SUPABASE_REST_URL']}/reporting_transactions?select=date,amount,type,category,account,notes"
    logger.debug(f"🔗 URL chamada: {url}")

    r = requests.get(url, headers=headers)
    logger.info(f"📥 Resposta Supabase: status={r.status_code}")
    if r.status_code != 200:
        logger.warning(f"❌ Conteúdo da resposta: {r.text}")
        return HttpResponse(f"❌ Erro Supabase: {r.status_code}", status=r.status_code)

    response = HttpResponse(r.content, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename=reporting.csv'
    return response
