"""Governance, audit and recalibration helpers for adaptive tuning."""

from __future__ import annotations

import datetime
import time
from typing import Any


def init_governance_state() -> dict[str, Any]:
    return {
        "policy_version": 1,
        "technical_committee": [],
        "owner": "unassigned",
        "approval_mode": "mixed",  # manual|mixed|auto_low_risk
        "audit_entries": [],
        "max_audit_entries": 500,
        "recalibration_schedule": {},
    }


def append_audit_entry(state: dict[str, Any], entry: dict[str, Any]) -> None:
    entries = state.get("audit_entries", [])
    entries.append(entry)
    state["audit_entries"] = entries[-int(state.get("max_audit_entries", 500)) :]


def current_period(now_ts: float | None = None) -> str:
    if now_ts is None:
        now_ts = time.time()
    dt = datetime.datetime.utcfromtimestamp(now_ts)
    return f"{dt.year:04d}-{dt.month:02d}"


def build_monthly_scorecard(
    stats: dict[str, Any], audit_entries: list[dict[str, Any]], period: str
) -> dict[str, Any]:
    cameras = stats.get("cameras", {}) if isinstance(stats, dict) else {}
    process_fps = []
    skipped_fps = []
    adaptive_overload = 0

    for camera_stats in cameras.values():
        if not isinstance(camera_stats, dict):
            continue
        process_fps.append(float(camera_stats.get("process_fps", 0.0) or 0.0))
        skipped_fps.append(float(camera_stats.get("skipped_fps", 0.0) or 0.0))
        adaptive_overload += int(camera_stats.get("adaptive_overload", 0) or 0)

    period_entries = [
        e for e in audit_entries if str(e.get("period", "")).strip() == period
    ]
    automatic_changes = len(
        [e for e in period_entries if e.get("origin") == "automatic"]
    )
    manual_changes = len([e for e in period_entries if e.get("origin") == "manual"])
    rollbacks = len([e for e in period_entries if e.get("action") == "rollback"])
    promotions = len([e for e in period_entries if e.get("action") == "promote"])

    avg_process = round(sum(process_fps) / len(process_fps), 2) if process_fps else 0.0
    avg_skipped = round(sum(skipped_fps) / len(skipped_fps), 2) if skipped_fps else 0.0

    return {
        "period": period,
        "cameras_count": len(cameras),
        "avg_process_fps": avg_process,
        "avg_skipped_fps": avg_skipped,
        "cameras_overloaded": adaptive_overload,
        "automatic_changes": automatic_changes,
        "manual_changes": manual_changes,
        "promotions": promotions,
        "rollbacks": rollbacks,
    }
