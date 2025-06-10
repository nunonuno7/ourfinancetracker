import os, requests, json
from .supabase_jwt import generate_supabase_jwt

SUPABASE_RPC_URL = f'{os.environ["SUPABASE_REST_URL"]}/rpc'

def call_rpc(user_id: int, fn_name: str, payload: dict | None = None) -> dict:
    token = generate_supabase_jwt(user_id=user_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": os.environ["SUPABASE_API_KEY"],
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    url = f"{SUPABASE_RPC_URL}/{fn_name}"
    resp = requests.post(url, headers=headers, json=payload or {})
    resp.raise_for_status()
    return resp.json()
