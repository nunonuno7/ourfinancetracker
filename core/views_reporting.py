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
    Public endpoint that accepts a short-lived JWT via the 'Authorization: Bearer <token>' header.
    For backwards compatibility, a 'token' query string is still accepted but will be removed.
    """
    # Prefer header over query string
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    token = ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    else:
        token = request.GET.get("token", "")  # deprecated fallback

    if not token:
        return HttpResponseForbidden("❌ Missing token.")

    try:
        service_role_key = get_env_or_fail("SUPABASE_SERVICE_ROLE_KEY")
        decoded = jwt.decode(token, service_role_key, algorithms=["HS256"])
        # Do not log decoded claims at INFO in production
        logger.debug("✅ Decoded original token claims.")
        user_id = decoded.get("sub")
        if not user_id:
            return HttpResponseForbidden("❌ Invalid JWT – missing 'sub'.")
    except jwt.ExpiredSignatureError:
        return HttpResponseForbidden("❌ Token expired.")
    except jwt.InvalidTokenError:
        return HttpResponseForbidden("❌ Invalid token.")
    except ImproperlyConfigured as e:
        logger.error(f"❌ Misconfiguration: {e}")
        return HttpResponse(str(e), status=500)

    # Mint a fresh 5-minute JWT scoped to the same subject
    fresh_payload = {
        "sub": str(user_id),
        "user_id": int(user_id),
        "role": "authenticated",
        "exp": datetime.utcnow() + timedelta(minutes=5),
    }
    fresh_token = jwt.encode(fresh_payload, service_role_key, algorithm="HS256")
    logger.debug("🔐 Minted fresh short-lived JWT for Supabase.")

    try:
        api_key = get_env_or_fail("SUPABASE_API_KEY")
        rest_url = get_env_or_fail("SUPABASE_REST_URL")
    except ImproperlyConfigured as e:
        logger.error(f"❌ Misconfiguration: {e}")
        return HttpResponse(str(e), status=500)

    headers = {
        "Authorization": f"Bearer {fresh_token}",
        "apikey": api_key,
        "Accept": "text/csv",
    }

    url = f"{rest_url}/reporting_transactions?select=date,amount,type,category,account,notes"
    r = requests.get(url, headers=headers)
    logger.info(f"📥 Supabase response status={r.status_code}")
    if r.status_code != 200:
        logger.warning(f"❌ Response body: {r.text}")
        return HttpResponse(f"❌ Supabase error: {r.status_code}", status=r.status_code)

    response = HttpResponse(r.content, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename=reporting.csv'
    # Avoid leaking tokens via Referer just in case
    response["Referrer-Policy"] = "no-referrer"
    return response
