from __future__ import annotations
import base64, hashlib, hmac, os
from datetime import datetime, timedelta, timezone
import jwt
from .config import settings

ALG='HS256'
def hash_password(password: str) -> str:
    salt=os.urandom(16); digest=hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 210_000)
    return 'pbkdf2_sha256$210000$'+base64.urlsafe_b64encode(salt).decode()+ '$'+base64.urlsafe_b64encode(digest).decode()
def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme,iters,salt,digest=encoded.split('$'); salt=base64.urlsafe_b64decode(salt); expected=base64.urlsafe_b64decode(digest)
        actual=hashlib.pbkdf2_hmac('sha256', password.encode(), salt, int(iters)); return hmac.compare_digest(actual, expected)
    except Exception: return False

def create_token(user_id: int) -> str:
    now=datetime.now(timezone.utc); return jwt.encode({'sub':str(user_id),'iat':now,'exp':now+timedelta(minutes=settings.jwt_expire_minutes)}, settings.jwt_secret, algorithm=ALG)
def decode_token(token: str) -> int:
    payload=jwt.decode(token, settings.jwt_secret, algorithms=[ALG]); return int(payload['sub'])
