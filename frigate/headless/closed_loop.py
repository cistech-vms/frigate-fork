"""Closed-loop optimization engine for adaptive tuning."""

from __future__ import annotations

import math
import time
from typing import Any

from frigate.headless.noise_intelligence import generate_noise_suggestions
from frigate.headless.runtime_config import CanaryPolicy


def init_closed_loop_state() -> dict[str, Any]:
    return {
        "enabled": True,
        "observation_interval_sec": 180,
        "reapply_cooldown_sec": 1800,
        "canary_duration_sec": 300,
        "freeze_on_incident_sec": 900,
        "freeze_on_rollback_sec": 1800,
        "rollback_streak_threshold": 2,
        "freeze_until_ts": 0.0,
        "last_run_ts": 0.0,
        "rollback_streak": 0,
        "last_applied": {},
        "last_decision": {"status": "idle"},
        "history": [],
        "max_history": 50,
    }


def _append_history(state: dict[str, Any], decision: dict[str, Any]) -> None:
    history = state.get("history", [])
    history.append(decision)
    state["history"] = history[-int(state.get("max_history", 50)) :]
    state["last_decision"] = decision


def _major_incident_detected(stats: dict[str, Any]) -> bool:
    cameras = stats.get("cameras", {}) if isinstance(stats, dict) else {}
    if not cameras:
        return False

    total = 0
    overloaded = 0
    for camera_stats in cameras.values():
        if not isinstance(camera_stats, dict):
            continue
        total += 1
        overload = int(camera_stats.get("adaptive_overload", 0) or 0)
        drops = int(camera_stats.get("routing_quota_drops", 0) or 0)
        skipped = float(camera_stats.get("skipped_fps", 0.0) or 0.0)
        if overload == 1 or drops > 5 or skipped >= 3.0:
            overloaded += 1

    if total == 0:
        return False

    threshold = max(2, math.ceil(total * 0.5))
    return overloaded >= threshold


def _choose_candidate_suggestion(
    suggestions: list[dict[str, Any]],
    state: dict[str, Any],
    now_ts: float,
) -> dict[str, Any] | None:
    cooldown = int(state.get("reapply_cooldown_sec", 1800))
    last_applied: dict[str, float] = state.get("last_applied", {})

    for item in suggestions:
        if item.get("risk") != "low":
            continue
        if not item.get("patch"):
            continue
        if item.get("type") not in {"threshold", "cooldown"}:
            continue
        key = f"{item.get('camera')}:{item.get('type')}"
        last_applied_ts = last_applied.get(key)
        if last_applied_ts is not None and (now_ts - float(last_applied_ts)) < cooldown:
            continue
        return item
    return None


def run_closed_loop_iteration(
    state: dict[str, Any],
    runtime_store,
    stats: dict[str, Any],
    effective_config: dict[str, Any],
    tenant_id: str,
    now_ts: float | None = None,
) -> dict[str, Any]:
    if now_ts is None:
        now_ts = time.time()

    if not state.get("enabled", True):
        decision = {"status": "disabled", "ts": int(now_ts)}
        _append_history(state, decision)
        return decision

    canary_status = runtime_store.evaluate_canary(stats, now_ts)
    canary_state = canary_status.get("status", "idle")

    if canary_state == "running":
        decision = {"status": "canary_running", "ts": int(now_ts)}
        _append_history(state, decision)
        return decision

    if canary_state == "rolled_back":
        state["rollback_streak"] = int(state.get("rollback_streak", 0)) + 1
        if state["rollback_streak"] >= int(state.get("rollback_streak_threshold", 2)):
            state["freeze_until_ts"] = now_ts + float(
                state.get("freeze_on_rollback_sec", 1800)
            )
            state["rollback_streak"] = 0
        decision = {
            "status": "rollback_detected",
            "reason": canary_status.get("reason"),
            "ts": int(now_ts),
        }
        _append_history(state, decision)
        return decision

    if canary_state == "promoted":
        state["rollback_streak"] = 0

    freeze_until = float(state.get("freeze_until_ts", 0.0))
    if now_ts < freeze_until:
        decision = {
            "status": "frozen",
            "freeze_remaining_sec": int(freeze_until - now_ts),
            "ts": int(now_ts),
        }
        _append_history(state, decision)
        return decision

    interval = int(state.get("observation_interval_sec", 180))
    last_run = float(state.get("last_run_ts", 0.0))
    if (now_ts - last_run) < interval:
        decision = {
            "status": "throttled",
            "next_run_in_sec": int(interval - (now_ts - last_run)),
            "ts": int(now_ts),
        }
        _append_history(state, decision)
        return decision

    state["last_run_ts"] = now_ts

    if _major_incident_detected(stats):
        freeze_sec = int(state.get("freeze_on_incident_sec", 900))
        state["freeze_until_ts"] = now_ts + freeze_sec
        decision = {
            "status": "incident_freeze",
            "freeze_sec": freeze_sec,
            "ts": int(now_ts),
        }
        _append_history(state, decision)
        return decision

    suggestions = generate_noise_suggestions(stats, effective_config, tenant_id)
    candidate = _choose_candidate_suggestion(suggestions, state, now_ts)
    if not candidate:
        decision = {"status": "no_candidate", "ts": int(now_ts)}
        _append_history(state, decision)
        return decision

    camera = str(candidate.get("camera"))
    policy = CanaryPolicy(
        cameras=[camera],
        duration_sec=int(state.get("canary_duration_sec", 300)),
        max_skipped_fps_increase=1.5,
        min_process_fps_ratio=0.8,
        max_inference_latency_increase_pct=25.0,
    )

    try:
        runtime_store.start_canary(candidate["patch"], policy, stats, now_ts)
    except Exception as exc:
        decision = {"status": "start_failed", "error": str(exc), "ts": int(now_ts)}
        _append_history(state, decision)
        return decision

    key = f"{candidate.get('camera')}:{candidate.get('type')}"
    state.setdefault("last_applied", {})[key] = now_ts
    decision = {
        "status": "started",
        "suggestion_id": candidate.get("id"),
        "camera": candidate.get("camera"),
        "type": candidate.get("type"),
        "ts": int(now_ts),
    }
    _append_history(state, decision)
    return decision
