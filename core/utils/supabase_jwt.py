# core/utils/supabase_jwt.py
import os, datetime, jwt           # pip install PyJWT
from typing import Any, Dict

def generate_supabase_jwt(user_id: int, role: str = "authenticated",
                          expires_minutes: int = 60) -> str:
    now = datetime.datetime.utcnow()
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "user_id": user_id,         # <= é este campo que a função SQL lê
        "role": role,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=expires_minutes),
    }
    secret = os.environ["SUPABASE_JWT_SECRET"]
    return jwt.encode(payload, secret, algorithm="HS256")
