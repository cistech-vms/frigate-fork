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


def get_headless_settings() -> HeadlessSettings:
    allowlist_raw = os.getenv("FRIGATE_CORS_ALLOWLIST", "")
    allowlist = [item.strip() for item in allowlist_raw.split(",") if item.strip()]
    auth_mode = os.getenv("FRIGATE_API_AUTH_MODE", "hmac").strip().lower()
    if auth_mode not in {"hmac", "jwt"}:
        raise ValueError("FRIGATE_API_AUTH_MODE must be 'hmac' or 'jwt'")
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
    )


def parse_typed_env_value(value: str):
    value = value.strip()
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
