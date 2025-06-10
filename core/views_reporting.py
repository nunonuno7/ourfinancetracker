import os
import jwt
import requests
from datetime import datetime, timedelta
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

@require_GET
@csrf_exempt
def proxy_report_csv_token(request):
    """
    Endpoint público que aceita um token JWT no URL:
    /reporting/data.csv?token=...

    Este token deve conter o 'sub' com o user_id.
    """
    token = request.GET.get("token", "")
    if not token:
        print("❌ Token em falta no pedido")
        return HttpResponseForbidden("❌ Token em falta.")

    try:
        # Validar o token original (assinado com service_role)
        decoded = jwt.decode(
            token,
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
            algorithms=["HS256"]
        )
        print(f"✅ Token original decodificado: {decoded}")

        user_id = decoded.get("sub")
        if not user_id:
            print("❌ JWT inválido – 'sub' ausente")
            return HttpResponseForbidden("❌ JWT inválido – sub ausente.")

    except jwt.ExpiredSignatureError:
        print("❌ Token expirado")
        return HttpResponseForbidden("❌ Token expirado.")
    except jwt.InvalidTokenError as e:
        print(f"❌ Token inválido: {e}")
        return HttpResponseForbidden("❌ Token inválido.")

    # Gerar novo JWT curto (5 min) com o mesmo sub
    fresh_payload = {
        "sub": str(user_id),                    # ainda útil como identificador padrão
        "user_id": int(user_id),                # 👈 essencial para funcionar com RLS
        "role": "authenticated",
        "exp": datetime.utcnow() + timedelta(minutes=5)
    }
    fresh_token = jwt.encode(
        fresh_payload,
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        algorithm="HS256"
    )
    print(f"🔐 Novo JWT gerado para Supabase: {fresh_token}")
    print(f"🧾 Payload JWT novo: {fresh_payload}")

    headers = {
        "Authorization": f"Bearer {fresh_token}",
        "apikey": os.environ["SUPABASE_API_KEY"],
        "Accept": "text/csv"
    }
    print(f"🔗 Headers enviados para Supabase: {headers}")

    url = f"{os.environ['SUPABASE_REST_URL']}/reporting_transactions?select=date,amount,type,category,account,notes"
    print(f"🔗 URL chamada: {url}")

    r = requests.get(url, headers=headers)
    print(f"📥 Resposta Supabase: status={r.status_code}")
    if r.status_code != 200:
        print(f"❌ Conteúdo da resposta: {r.text}")
        return HttpResponse(f"❌ Erro Supabase: {r.status_code}", status=r.status_code)

    response = HttpResponse(r.content, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename=reporting.csv'
    return response
