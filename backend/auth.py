"""Auth primitives: password hashing + signed-cookie sessions."""
import os
from typing import Optional
import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request, HTTPException, Response
from database import get_db

# 30-day sliding session
SESSION_MAX_AGE = 60 * 60 * 24 * 30
COOKIE_NAME = "argamag_session"

# SECRET_KEY: from env in prod; dev fallback for localhost.
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = "dev-secret-change-me-in-production-" + "x" * 16
    print("⚠️  Using DEV SECRET_KEY. Set SECRET_KEY env var in production.")

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="argamag-session")

# bcrypt has a 72-byte input limit. We truncate to be safe — passwords longer
# than that are still usable, just only the first 72 bytes are significant.
def _encode_password(plain: str) -> bytes:
    return plain.encode("utf-8")[:72]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_encode_password(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_encode_password(plain), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_session_token(user_id: int) -> str:
    return _serializer.dumps({"uid": user_id})


def read_session_token(token: str) -> Optional[int]:
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE)
        return int(data["uid"])
    except (BadSignature, SignatureExpired, KeyError, ValueError, TypeError):
        return None


def set_session_cookie(response: Response, user_id: int):
    token = create_session_token(user_id)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        # secure=True will be set automatically by the reverse proxy in prod
        # (Fly.io). We don't set it here so it works on localhost HTTP too.
    )


def clear_session_cookie(response: Response):
    response.delete_cookie(COOKIE_NAME)


def current_user(request: Request) -> dict:
    """FastAPI dependency: returns user dict, raises 401 if not authenticated."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Not authenticated")
    user_id = read_session_token(token)
    if user_id is None:
        raise HTTPException(401, "Invalid or expired session")
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, full_name, active, role, contact_id, trainer_id "
        "FROM user WHERE id=?", (user_id,)
    ).fetchone()
    conn.close()
    if not row or not row["active"]:
        raise HTTPException(401, "User not found or deactivated")
    return dict(row)
