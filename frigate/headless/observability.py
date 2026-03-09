import time
from typing import Any


def build_observability_snapshot(
    *,
    readiness: dict[str, Any],
    delivery_status: dict[str, Any],
    rate_limit_audit: list[dict[str, Any]],
    storage_sync: dict[str, Any],
) -> dict[str, Any]:
    now = int(time.time())
    backlog = int(delivery_status.get("pending_total", 0))
    rate_limited = len(
        [item for item in rate_limit_audit[-200:] if item.get("event") == "rate_limit_rejected"]
    )
    errors = int(delivery_status.get("channels", {}).get("webhook", {}).get("failed", 0))
    throughput = int(storage_sync.get("throughput", 0))
    return {
        "ts": now,
        "readiness_mode": readiness.get("mode", "unknown"),
        "api_ready": bool(readiness.get("ready", False)),
        "event_backlog": backlog,
        "event_webhook_failures": errors,
        "rate_limit_rejections_recent": rate_limited,
        "storage_sync_throughput": throughput,
        "storage_sync_failures": int(storage_sync.get("failures", 0)),
        "slo": {
            "event_backlog_ok": backlog <= 500,
            "rate_limit_rejections_ok": rate_limited <= 200,
            "storage_sync_ok": int(storage_sync.get("failures", 0)) <= 100,
        },
    }


def evaluate_release_gate(snapshot: dict[str, Any]) -> dict[str, Any]:
    slo = snapshot.get("slo", {})
    failed = [name for name, ok in slo.items() if not ok]
    passed = len(failed) == 0 and bool(snapshot.get("api_ready", False))
    reasons: list[str] = []
    if not snapshot.get("api_ready", False):
        reasons.append("api_not_ready")
    reasons.extend([f"slo_failed:{name}" for name in failed])
    return {
        "passed": passed,
        "reasons": reasons,
        "snapshot": snapshot,
    }
