"""JWT auth utilities.

Env variables:
- RAG_JWT_SECRET (required to enable JWT auth)
- RAG_JWT_ALG (default: HS256)
- RAG_JWT_EXPIRE_SECONDS (default: 3600)
- RAG_ALLOWED_USERS (comma list, optional – if set restricts valid sub)
- RAG_ALLOWED_ROLES (comma list of acceptable roles, optional)
- RAG_DEFAULT_ROLE (role assigned if none specified, default: user)
- RAG_ROLE_MAP_JSON (optional JSON {"user":"role", ...} to override default role per user)

Endpoints use dependency `require_jwt` when enabled.
If secret is missing -> open mode (no auth enforced).
"""
from __future__ import annotations

import os
import time
import json
from typing import Optional, Dict, Any, Set
import jwt
from fastapi import HTTPException, status, Header

class JWTConfig:
    def __init__(self):
        self.secret = os.getenv("RAG_JWT_SECRET")
        self.alg = os.getenv("RAG_JWT_ALG", "HS256")
        try:
            self.expire_seconds = int(os.getenv("RAG_JWT_EXPIRE_SECONDS", "3600"))
        except ValueError:
            self.expire_seconds = 3600
        self.allowed_users: Optional[Set[str]] = None
        au = os.getenv("RAG_ALLOWED_USERS")
        if au:
            self.allowed_users = {u.strip() for u in au.split(',') if u.strip()}
        ar = os.getenv("RAG_ALLOWED_ROLES")
        self.allowed_roles: Optional[Set[str]] = None
        if ar:
            self.allowed_roles = {r.strip() for r in ar.split(',') if r.strip()}
        self.default_role = os.getenv("RAG_DEFAULT_ROLE", "user")
        role_map_raw = os.getenv("RAG_ROLE_MAP_JSON")
        self.role_map: Dict[str, str] = {}
        if role_map_raw:
            try:
                self.role_map = json.loads(role_map_raw)
            except Exception:  # noqa: BLE001
                self.role_map = {}

    def enabled(self) -> bool:
        return bool(self.secret)

_jwt_cfg = JWTConfig()


def refresh_config():  # for hot reload if env changes
    global _jwt_cfg
    _jwt_cfg = JWTConfig()


def _resolve_role(user: str, requested_role: Optional[str]) -> str:
    # precedence: explicit requested (if allowed) > role_map > default
    if requested_role:
        if _jwt_cfg.allowed_roles and requested_role not in _jwt_cfg.allowed_roles:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role not allowed")
        return requested_role
    mapped = _jwt_cfg.role_map.get(user)
    if mapped:
        return mapped
    # if mapped role not allowed -> fallback default
    if _jwt_cfg.allowed_roles and _jwt_cfg.default_role not in _jwt_cfg.allowed_roles:
        # pick any allowed role (first) as fallback
        return next(iter(_jwt_cfg.allowed_roles))
    return _jwt_cfg.default_role


def issue_token(sub: str, claims: Optional[Dict[str, Any]] = None, role: Optional[str] = None) -> str:
    if not _jwt_cfg.enabled():
        raise RuntimeError("JWT auth not enabled (RAG_JWT_SECRET missing)")
    if _jwt_cfg.allowed_users and sub not in _jwt_cfg.allowed_users:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not allowed")
    role_final = _resolve_role(sub, role)
    if _jwt_cfg.allowed_roles and role_final not in _jwt_cfg.allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not allowed (post resolution)")
    now = int(time.time())
    payload = {
        "sub": sub,
        "role": role_final,
        "iat": now,
        "exp": now + _jwt_cfg.expire_seconds,
        "iss": "lightrag",
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, _jwt_cfg.secret, algorithm=_jwt_cfg.alg)  # type: ignore[arg-type]


def verify_token(token: str) -> Dict[str, Any]:
    if not _jwt_cfg.enabled():
        return {"sub": "anonymous", "role": "open", "mode": "open"}
    try:
        decoded = jwt.decode(token, _jwt_cfg.secret, algorithms=[_jwt_cfg.alg])  # type: ignore[arg-type]
        sub = decoded.get('sub')
        role = decoded.get('role')
        if _jwt_cfg.allowed_users and sub not in _jwt_cfg.allowed_users:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not allowed anymore")
        if _jwt_cfg.allowed_roles and role not in _jwt_cfg.allowed_roles:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Role not allowed anymore")
        return decoded
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def require_jwt(authorization: str | None = Header(default=None)):
    # Если секрет не задан и не требуется строго – работаем в open режиме.
    # Если включён флаг строгого режима (RAG_REQUIRE_JWT=1) – блокируем доступ.
    if not _jwt_cfg.enabled():  # open mode unless strict required
        if os.getenv("RAG_REQUIRE_JWT", "0").lower() in {"1", "true", "yes"}:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="JWT auth disabled (set RAG_JWT_SECRET)")
        return {"sub": "open", "role": "open", "mode": "open"}
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    return verify_token(token)

