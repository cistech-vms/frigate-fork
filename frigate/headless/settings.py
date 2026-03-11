import json
import os
from dataclasses import dataclass


def _parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class HeadlessSettings:
    enabled: bool
    auth_mode: str
    hmac_max_skew_sec: int
    rate_limit_per_minute: int
    tenant_id: str | None
    cors_allowlist: list[str]
    metrics_enabled: bool
    readiness_warmup_sec: int
    readiness_min_process_fps: float
    readiness_max_skipped_process_ratio: float
    readiness_max_sse_fill_ratio: float
    rate_limit_block_base_sec: int
    rate_limit_block_max_sec: int
    cms_enabled: bool
    cms_required: bool
    cms_url: str | None
    cms_tenant_code: str | None
    cms_auth_mode: str
    cms_token: str | None
    cms_username: str | None
    cms_password: str | None
    cms_sync_interval_sec: int
    cms_request_timeout_sec: float
    cms_license_grace_sec: int


def get_headless_settings() -> HeadlessSettings:
    allowlist_raw = os.getenv("FRIGATE_CORS_ALLOWLIST", "")
    allowlist = [item.strip() for item in allowlist_raw.split(",") if item.strip()]
    auth_mode = os.getenv("FRIGATE_API_AUTH_MODE", "hmac").strip().lower()
    if auth_mode not in {"hmac", "jwt"}:
        raise ValueError("FRIGATE_API_AUTH_MODE must be 'hmac' or 'jwt'")
    cms_url = (os.getenv("FRIGATE_CMS_URL", "") or "").strip() or None
    cms_required = _parse_bool(os.getenv("FRIGATE_CMS_REQUIRED", "false"), default=False)
    cms_enabled = bool(cms_url)
    cms_auth_mode = (os.getenv("FRIGATE_CMS_AUTH_MODE", "token") or "").strip().lower()
    if cms_auth_mode not in {"token", "password"}:
        raise ValueError("FRIGATE_CMS_AUTH_MODE must be 'token' or 'password'")
    cms_tenant_code = (os.getenv("FRIGATE_TENANT_CODE", "") or "").strip() or None
    cms_token = (os.getenv("FRIGATE_CMS_TOKEN", "") or "").strip() or None
    cms_username = (os.getenv("FRIGATE_CMS_USERNAME", "") or "").strip() or None
    cms_password = (os.getenv("FRIGATE_CMS_PASSWORD", "") or "").strip() or None
    cms_sync_interval_sec = int(os.getenv("FRIGATE_CMS_SYNC_INTERVAL_SEC", "60"))
    cms_request_timeout_sec = float(os.getenv("FRIGATE_CMS_REQUEST_TIMEOUT_SEC", "8.0"))
    cms_license_grace_sec = int(os.getenv("FRIGATE_CMS_LICENSE_GRACE_SEC", "900"))
    if cms_enabled or cms_required:
        if not cms_url:
            raise ValueError("FRIGATE_CMS_URL is required when CMS mode is enabled/required")
        if not cms_tenant_code:
            raise ValueError("FRIGATE_TENANT_CODE is required when CMS mode is enabled/required")
        if cms_auth_mode == "token" and not cms_token:
            raise ValueError(
                "FRIGATE_CMS_TOKEN is required when FRIGATE_CMS_AUTH_MODE=token and CMS mode is enabled/required"
            )
        if cms_auth_mode == "password" and (not cms_username or not cms_password):
            raise ValueError(
                "FRIGATE_CMS_USERNAME and FRIGATE_CMS_PASSWORD are required when FRIGATE_CMS_AUTH_MODE=password and CMS mode is enabled/required"
            )
    return HeadlessSettings(
        # Headless is mandatory in this distribution profile.
        enabled=True,
        auth_mode=auth_mode,
        hmac_max_skew_sec=int(os.getenv("FRIGATE_API_HMAC_MAX_SKEW_SEC", "300")),
        rate_limit_per_minute=int(os.getenv("FRIGATE_API_RATE_LIMIT_PER_MIN", "120")),
        tenant_id=os.getenv("FRIGATE_TENANT_ID"),
        cors_allowlist=allowlist,
        metrics_enabled=_parse_bool(os.getenv("FRIGATE_METRICS_ENABLED", "true"), default=True),
        readiness_warmup_sec=int(os.getenv("FRIGATE_READINESS_WARMUP_SEC", "20")),
        readiness_min_process_fps=float(os.getenv("FRIGATE_READINESS_MIN_PROCESS_FPS", "0.1")),
        readiness_max_skipped_process_ratio=float(
            os.getenv("FRIGATE_READINESS_MAX_SKIPPED_PROCESS_RATIO", "2.0")
        ),
        readiness_max_sse_fill_ratio=float(
            os.getenv("FRIGATE_READINESS_MAX_SSE_FILL_RATIO", "0.95")
        ),
        rate_limit_block_base_sec=int(os.getenv("FRIGATE_API_RATE_LIMIT_BLOCK_BASE_SEC", "30")),
        rate_limit_block_max_sec=int(os.getenv("FRIGATE_API_RATE_LIMIT_BLOCK_MAX_SEC", "900")),
        cms_enabled=cms_enabled,
        cms_required=cms_required,
        cms_url=cms_url,
        cms_tenant_code=cms_tenant_code,
        cms_auth_mode=cms_auth_mode,
        cms_token=cms_token,
        cms_username=cms_username,
        cms_password=cms_password,
        cms_sync_interval_sec=max(5, cms_sync_interval_sec),
        cms_request_timeout_sec=max(1.0, cms_request_timeout_sec),
        cms_license_grace_sec=max(0, cms_license_grace_sec),
    )


def parse_typed_env_value(value: str):
    value = value.strip()
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
