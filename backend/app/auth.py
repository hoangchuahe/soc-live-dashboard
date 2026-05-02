"""
JWT authentication + role-based access control.

Two roles modelled after Tier 1 / Tier 2 SOC analyst workflows (the same
pattern I built at PNO):
  - viewer  → read-only access to all GETs
  - admin   → can ack / close alerts, reload rules, prune events

Public endpoints (/health, /metrics, /ws, /api/topology, /api/events/*)
remain unauthenticated for the demo. Mutating endpoints require auth.

Demo credentials (replace in prod via env vars):
  POST /api/auth/login  { "username": "admin",  "password": "admin"  }
  POST /api/auth/login  { "username": "viewer", "password": "viewer" }
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# ── Config ────────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("JWT_SECRET", "demo-secret-change-me-in-prod")
ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 8

# Demo user store. Real deployment would back this with a `users` table +
# bcrypt-hashed passwords. Hashes here are SHA-256(password) for simplicity —
# do not copy this pattern verbatim into a production codebase.
def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


_USERS: dict[str, dict] = {
    "admin":  {"password_hash": _hash(os.getenv("ADMIN_PASSWORD",  "admin")),  "role": "admin"},
    "viewer": {"password_hash": _hash(os.getenv("VIEWER_PASSWORD", "viewer")), "role": "viewer"},
}

bearer_scheme = HTTPBearer(auto_error=False)


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    expires_in: int   # seconds


class UserInfo(BaseModel):
    username: str
    role: str


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(username: str, role: str) -> tuple[str, int]:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
    payload = {
        "sub": username,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, TOKEN_TTL_HOURS * 3600


def authenticate(username: str, password: str) -> str | None:
    """Returns role on success, None on failure."""
    user = _USERS.get(username)
    if not user:
        return None
    if not hmac.compare_digest(user["password_hash"], _hash(password)):
        return None
    return user["role"]


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


# ── FastAPI dependencies ──────────────────────────────────────────────────────

async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserInfo:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    return UserInfo(username=payload["sub"], role=payload["role"])


def require_role(*allowed_roles: str):
    """Return a FastAPI dependency that enforces one of the listed roles."""
    async def _checker(user: UserInfo = Depends(current_user)) -> UserInfo:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' not permitted; need one of {list(allowed_roles)}",
            )
        return user
    return _checker


require_admin = require_role("admin")
require_any_user = require_role("admin", "viewer")
