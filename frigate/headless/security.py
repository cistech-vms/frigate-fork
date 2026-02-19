import hmac
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

from fastapi import HTTPException, Request
from joserfc import jwt
from joserfc.jwk import OctKey

from .settings import HeadlessSettings

logger = logging.getLogger(__name__)


@dataclass
class Principal:
    subject: str
    role: str
    tenant_id: str | None


class SimpleRateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit_per_minute = max(1, limit_per_minute)
        self._buckets: dict[str, tuple[int, int]] = {}
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now_minute = int(time.time() // 60)
        with self._lock:
            minute, count = self._buckets.get(key, (now_minute, 0))
            if minute != now_minute:
                minute, count = now_minute, 0
            count += 1
            self._buckets[key] = (minute, count)
            return count <= self.limit_per_minute


def _load_hmac_keys() -> dict[str, dict[str, str]]:
    raw = os.getenv("FRIGATE_API_HMAC_KEYS_JSON", "")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        logger.error("FRIGATE_API_HMAC_KEYS_JSON is not valid JSON")
    return {}


def _verify_hmac(request: Request, settings: HeadlessSettings) -> Principal:
    key_id = request.headers.get("x-key-id")
    signature = request.headers.get("x-signature", "")
    ts_header = request.headers.get("x-timestamp", "")

    if not key_id or not signature or not ts_header:
        raise HTTPException(status_code=401, detail="Missing HMAC authentication headers")

    try:
        ts = int(ts_header)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid x-timestamp") from exc

    now = int(time.time())
    if abs(now - ts) > settings.hmac_max_skew_sec:
        raise HTTPException(status_code=401, detail="Timestamp outside allowed skew")

    keys = _load_hmac_keys()
    key_config = keys.get(key_id)
    if not key_config:
        raise HTTPException(status_code=401, detail="Invalid key id")

    secret = key_config.get("secret", "")
    role = key_config.get("role", "reader")
    tenant_id = key_config.get("tenant_id")

    body = getattr(request.state, "raw_body", b"")
    expected = hashlib.sha256(body + ts_header.encode("utf-8") + secret.encode("utf-8")).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    return Principal(subject=key_id, role=role, tenant_id=tenant_id)


def _verify_jwt(request: Request) -> Principal:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = auth.replace("Bearer ", "", 1).strip()
    secret = os.getenv("FRIGATE_API_JWT_SECRET", "")
    if not secret:
        raise HTTPException(status_code=500, detail="JWT secret not configured")

    jwt_key = OctKey.import_key(secret.encode("utf-8"))

    try:
        decoded = jwt.decode(token, jwt_key)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    role = decoded.claims.get("role", "reader")
    sub = decoded.claims.get("sub", "anonymous")
    tenant_id = decoded.claims.get("tenant_id")
    exp = decoded.claims.get("exp")
    if exp and int(exp) <= int(time.time()):
        raise HTTPException(status_code=401, detail="Token expired")

    return Principal(subject=sub, role=role, tenant_id=tenant_id)


def require_role(role: str):
    role_order = {"reader": 0, "admin": 1}

    async def checker(request: Request) -> Principal:
        settings: HeadlessSettings = request.app.state.headless_settings
        limiter: SimpleRateLimiter = request.app.state.headless_rate_limiter

        remote = request.client.host if request.client else "unknown"
        auth_hint = request.headers.get("x-key-id") or request.headers.get("authorization", remote)

        if not limiter.allow(f"{remote}:{auth_hint}"):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        mode = settings.auth_mode
        if mode == "hmac":
            principal = _verify_hmac(request, settings)
        elif mode == "jwt":
            principal = _verify_jwt(request)
        else:
            principal = Principal(subject="anonymous", role="admin", tenant_id=settings.tenant_id)

        if role_order.get(principal.role, -1) < role_order.get(role, 99):
            raise HTTPException(status_code=403, detail="Insufficient role")

        request.state.principal = principal
        return principal

    return checker


def resolve_tenant(request: Request, requested_tenant: str | None = None) -> str:
    settings: HeadlessSettings = request.app.state.headless_settings
    principal: Principal | None = getattr(request.state, "principal", None)

    if settings.tenant_id:
        if requested_tenant and requested_tenant != settings.tenant_id:
            raise HTTPException(status_code=403, detail="Tenant mismatch for this instance")
        return settings.tenant_id

    tenant = requested_tenant or request.headers.get("x-tenant-id")
    if not tenant:
        raise HTTPException(status_code=400, detail="tenant_id is required")

    if principal and principal.tenant_id and principal.tenant_id != tenant:
        raise HTTPException(status_code=403, detail="Tenant mismatch for token/key")

    return tenant
