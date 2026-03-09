"""Headless runtime API for Frigate core engine."""

import copy
import json
import logging
import queue
import time
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from frigate.config.camera.updater import (
    CameraConfigUpdateEnum,
    CameraConfigUpdateTopic,
)
from frigate.headless.runtime_config import (
    CanaryPolicy,
    diff_top_level_keys,
    requires_restart,
)
from frigate.headless.noise_intelligence import generate_noise_suggestions
from frigate.headless.observability import (
    build_observability_snapshot,
    evaluate_release_gate,
)
from frigate.headless.closed_loop import run_closed_loop_iteration
from frigate.headless.governance import (
    append_audit_entry,
    build_monthly_scorecard,
    current_period,
)
from frigate.headless.self_healing import (
    register_chaos_event,
    register_recovery,
    should_recover,
)
from frigate.headless.readiness import evaluate_readiness
from frigate.headless.security import Principal, require_role, resolve_tenant
from frigate.stats.prometheus import get_metrics, update_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["headless"])
ops_router = APIRouter(tags=["headless-ops"])


class ConfigApplyRequest(BaseModel):
    tenant_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    canary: bool = False
    canary_cameras: list[str] = Field(default_factory=list)
    canary_duration_sec: int = Field(default=300, ge=30, le=3600)
    canary_max_skipped_fps_increase: float = Field(default=2.0, ge=0.0)
    canary_min_process_fps_ratio: float = Field(default=0.7, ge=0.1, le=1.0)
    canary_max_inference_latency_increase_pct: float = Field(default=35.0, ge=0.0)


class ConfigValidateRequest(BaseModel):
    tenant_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class SuggestionApproveRequest(BaseModel):
    tenant_id: str | None = None
    auto_approve: bool = False


class ClosedLoopControlRequest(BaseModel):
    enabled: bool | None = None
    observation_interval_sec: int | None = Field(default=None, ge=30, le=3600)
    freeze_sec: int | None = Field(default=None, ge=0, le=86400)


class GovernancePolicyRequest(BaseModel):
    policy_version: int | None = Field(default=None, ge=1)
    owner: str | None = None
    approval_mode: Literal["manual", "mixed", "auto_low_risk"] | None = None
    technical_committee: list[str] | None = None


class RecalibrationScheduleRequest(BaseModel):
    segment: str
    cameras: list[str] = Field(default_factory=list)
    frequency_days: int = Field(default=30, ge=1, le=365)
    owner: str = Field(default="unassigned")
    enabled: bool = True


class ChaosInjectionRequest(BaseModel):
    scenario: Literal[
        "delivery_worker_restart",
        "simulate_webhook_failure",
        "simulate_backpressure",
    ]


class StorageConfigRequest(BaseModel):
    tenant_id: str | None = None
    provider: Literal["local", "s3", "r2"] = "local"
    bucket: str | None = None
    region: str | None = None
    endpoint: str | None = None
    prefix: str | None = None


def _apply_zones_hot_reload(request: Request, patch: dict[str, Any]) -> None:
    cameras_patch = patch.get("cameras", {}) if isinstance(patch, dict) else {}
    for camera_name, camera_patch in cameras_patch.items():
        zones = camera_patch.get("zones") if isinstance(camera_patch, dict) else None
        if zones is None:
            continue
        if camera_name not in request.app.frigate_config.cameras:
            continue
        request.app.frigate_config.cameras[camera_name].zones = zones
        request.app.config_publisher.publish_update(
            CameraConfigUpdateTopic(CameraConfigUpdateEnum.zones, camera_name),
            zones,
        )


def _runtime_tenant(request: Request, tenant_id: str | None = None) -> str:
    if tenant_id:
        request.app.state.headless_runtime_tenant = tenant_id
        return tenant_id
    return str(getattr(request.app.state, "headless_runtime_tenant", "default"))


def _persist_runtime_overlay(request: Request, tenant_id: str | None = None) -> None:
    request.app.state.headless_state_store.put_runtime_overlay(
        _runtime_tenant(request, tenant_id),
        request.app.state.runtime_config_store.runtime_overlay,
    )


def _persist_triggers(request: Request) -> None:
    request.app.state.headless_state_store.put_triggers(request.app.state.headless_triggers)


def _persist_regions(request: Request) -> None:
    request.app.state.headless_state_store.put_regions(request.app.state.headless_regions)


def _compute_readiness(request: Request) -> dict[str, Any]:
    settings = request.app.state.headless_settings
    stats = request.app.stats_emitter.get_latest_stats()
    before_overlay = copy.deepcopy(request.app.state.runtime_config_store.runtime_overlay)
    canary_status = request.app.state.runtime_config_store.evaluate_canary(stats, time.time())
    if request.app.state.runtime_config_store.runtime_overlay != before_overlay:
        _persist_runtime_overlay(request)
    snapshot = evaluate_readiness(
        stats=stats,
        db_connected=not request.app.database.is_closed(),
        sse_health=request.app.state.sse_client.stream_health(),
        canary_status=canary_status,
        started_at=request.app.state.headless_started_at,
        warmup_sec=settings.readiness_warmup_sec,
        min_process_fps=settings.readiness_min_process_fps,
        max_skipped_process_ratio=settings.readiness_max_skipped_process_ratio,
        max_sse_fill_ratio=settings.readiness_max_sse_fill_ratio,
    )
    request.app.state.headless_readiness = snapshot
    if not snapshot.get("ready", False) or snapshot.get("mode") == "degraded_read_only":
        _self_heal_if_needed(request, reason=f"readiness:{snapshot.get('mode')}")
    return snapshot


def _ensure_write_allowed(request: Request) -> None:
    readiness = _compute_readiness(request)
    if readiness.get("write_critical_allowed"):
        return
    raise HTTPException(
        status_code=503,
        detail={
            "error": "Write operations temporarily blocked by readiness gate",
            "mode": readiness.get("mode"),
            "reasons": readiness.get("reasons", []),
            "warnings": readiness.get("warnings", []),
        },
    )


def _self_heal_if_needed(request: Request, reason: str) -> None:
    state: dict[str, Any] = request.app.state.headless_self_healing
    if not should_recover(state):
        return
    request.app.state.reliable_delivery.process_due()
    request.app.state.storage_sync.process_due()
    register_recovery(state, action="reconcile_workers", reason=reason)


class TriggerAction(BaseModel):
    type: Literal["webhook", "mqtt", "kafka", "clip", "snapshot", "internal_callback"]
    target: str | None = None
    payload_template: dict[str, Any] | None = None


class TriggerModel(BaseModel):
    id: str
    tenant_id: str
    camera_id: str
    event_types: list[
        Literal[
            "person",
            "car",
            "motion",
            "loitering",
            "line-crossing",
            "zone-enter",
            "zone-exit",
        ]
    ]
    time_window: dict[str, Any] = Field(default_factory=dict)
    cooldown_sec: int = 0
    threshold: float = 0.0
    debounce_ms: int = 0
    actions: list[TriggerAction] = Field(default_factory=list)
    enabled: bool = True


class RegionShape(BaseModel):
    type: Literal["polygon", "bbox", "mask"]
    points: list[list[float]] | None = None
    bbox: list[float] | None = None
    mask: str | None = None


class RegionModel(BaseModel):
    id: str
    tenant_id: str
    camera_id: str
    shape: RegionShape
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/status", dependencies=[Depends(require_role("reader"))])
def status(request: Request):
    stats = request.app.stats_emitter.get_latest_stats()
    before_overlay = copy.deepcopy(request.app.state.runtime_config_store.runtime_overlay)
    canary = request.app.state.runtime_config_store.evaluate_canary(stats, time.time())
    if request.app.state.runtime_config_store.runtime_overlay != before_overlay:
        _persist_runtime_overlay(request)
    loop_state = request.app.state.headless_closed_loop
    tenant_id = request.app.state.headless_settings.tenant_id or "default"
    loop_decision = run_closed_loop_iteration(
        loop_state,
        request.app.state.runtime_config_store,
        stats,
        request.app.state.runtime_config_store.effective_dict(),
        tenant_id,
        now_ts=time.time(),
    )
    gov_state: dict[str, Any] = request.app.state.headless_governance
    if loop_decision.get("status") == "started":
        append_audit_entry(
            gov_state,
            {
                "ts": int(time.time()),
                "period": current_period(),
                "origin": "automatic",
                "action": "apply",
                "source": "closed_loop",
                "suggestion_id": loop_decision.get("suggestion_id"),
                "camera": loop_decision.get("camera"),
                "change_type": loop_decision.get("type"),
            },
        )
    if canary.get("status") == "promoted":
        append_audit_entry(
            gov_state,
            {
                "ts": int(time.time()),
                "period": current_period(),
                "origin": "automatic",
                "action": "promote",
                "source": "canary",
                "canary_id": canary.get("id"),
            },
        )
    if canary.get("status") == "rolled_back":
        append_audit_entry(
            gov_state,
            {
                "ts": int(time.time()),
                "period": current_period(),
                "origin": "automatic",
                "action": "rollback",
                "source": "canary",
                "canary_id": canary.get("id"),
                "reason": canary.get("reason"),
            },
        )
    return JSONResponse(
        content={
            "uptime_sec": int(time.time() - request.app.state.headless_started_at),
            "version": request.app.frigate_config.version,
            "cameras": list(request.app.frigate_config.cameras.keys()),
            "stats": stats,
            "canary": canary,
            "closed_loop": {
                "enabled": bool(loop_state.get("enabled", True)),
                "decision": loop_decision,
                "freeze_until_ts": int(loop_state.get("freeze_until_ts", 0.0)),
            },
            "headless": True,
        }
    )


@router.get("/config/effective", dependencies=[Depends(require_role("reader"))])
def config_effective(request: Request):
    store = request.app.state.runtime_config_store
    return JSONResponse(content=store.effective_dict())


@router.post("/config/validate", dependencies=[Depends(require_role("admin"))])
def config_validate(request: Request, body: ConfigValidateRequest):
    _ensure_write_allowed(request)
    tenant_id = resolve_tenant(request, body.tenant_id)
    del tenant_id
    store = request.app.state.runtime_config_store

    try:
        store.validate_candidate(body.config)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return JSONResponse(content={"valid": True})


@router.post("/config/apply", dependencies=[Depends(require_role("admin"))])
def config_apply(request: Request, body: ConfigApplyRequest):
    _ensure_write_allowed(request)
    tenant_id = resolve_tenant(request, body.tenant_id)
    active_tenant = _runtime_tenant(request, tenant_id)
    del tenant_id

    store = request.app.state.runtime_config_store
    before = store.effective_dict()

    try:
        if body.canary:
            policy = CanaryPolicy(
                cameras=body.canary_cameras,
                duration_sec=body.canary_duration_sec,
                max_skipped_fps_increase=body.canary_max_skipped_fps_increase,
                min_process_fps_ratio=body.canary_min_process_fps_ratio,
                max_inference_latency_increase_pct=body.canary_max_inference_latency_increase_pct,
            )
            latest_stats = request.app.stats_emitter.get_latest_stats()
            _, applied_patch, canary_status = store.start_canary(
                body.config, policy, latest_stats, time.time()
            )
            _apply_zones_hot_reload(request, applied_patch)
            _persist_runtime_overlay(request, active_tenant)
            after = store.effective_dict()
            changed = diff_top_level_keys(before, after)
            restart_needed = requires_restart(changed)
            return JSONResponse(
                content={
                    "requires_restart": restart_needed,
                    "changes": changed,
                    "message": "Canary rollout started",
                    "canary": canary_status,
                }
            )
        store.apply_runtime_patch(body.config)
        _persist_runtime_overlay(request, active_tenant)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    after = store.effective_dict()
    changed = diff_top_level_keys(before, after)
    restart_needed = requires_restart(changed)

    # Apply hot reload for zones only.
    _apply_zones_hot_reload(request, body.config)
    append_audit_entry(
        request.app.state.headless_governance,
        {
            "ts": int(time.time()),
            "period": current_period(),
            "origin": "manual",
            "action": "apply",
            "source": "config_apply",
            "changes": changed,
            "requires_restart": restart_needed,
        },
    )

    message = "Configuration applied with hot reload where supported"
    if restart_needed:
        message = "Configuration accepted, but one or more changes require process restart"

    return JSONResponse(
        content={
            "requires_restart": restart_needed,
            "changes": changed,
            "message": message,
        }
    )


@router.get("/config/canary/status", dependencies=[Depends(require_role("reader"))])
def config_canary_status(request: Request):
    stats = request.app.stats_emitter.get_latest_stats()
    before_overlay = copy.deepcopy(request.app.state.runtime_config_store.runtime_overlay)
    result = request.app.state.runtime_config_store.evaluate_canary(stats, time.time())
    if request.app.state.runtime_config_store.runtime_overlay != before_overlay:
        _persist_runtime_overlay(request)
    return JSONResponse(content=result)


@router.post("/config/canary/rollback", dependencies=[Depends(require_role("admin"))])
def config_canary_rollback(request: Request):
    _ensure_write_allowed(request)
    resolve_tenant(request)
    stats = request.app.stats_emitter.get_latest_stats()
    result = request.app.state.runtime_config_store.rollback_canary(
        "Manual rollback requested", stats, time.time()
    )
    _persist_runtime_overlay(request)
    append_audit_entry(
        request.app.state.headless_governance,
        {
            "ts": int(time.time()),
            "period": current_period(),
            "origin": "manual",
            "action": "rollback",
            "source": "canary",
            "reason": "Manual rollback requested",
        },
    )
    return JSONResponse(content=result)


@router.post("/reload", dependencies=[Depends(require_role("admin"))])
def reload_supported_components(request: Request):
    _ensure_write_allowed(request)
    resolve_tenant(request)
    # Hot reload supported here is currently limited to regions/zones and triggers.
    return JSONResponse(
        content={
            "reloaded": ["regions", "triggers"],
            "requires_restart": False,
        }
    )


@router.post("/triggers/upsert", dependencies=[Depends(require_role("admin"))])
def upsert_trigger(request: Request, body: TriggerModel):
    _ensure_write_allowed(request)
    tenant_id = resolve_tenant(request, body.tenant_id)
    if tenant_id != body.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    store: dict[str, dict[str, Any]] = request.app.state.headless_triggers
    trigger = body.model_dump(mode="json")
    store[body.id] = trigger
    _persist_triggers(request)

    # Emit update event to stream subscribers.
    event_id = request.app.state.reliable_delivery.emit("triggers/upsert", trigger)

    return JSONResponse(content={"success": True, "trigger": trigger, "event_id": event_id})


@router.get("/triggers", dependencies=[Depends(require_role("reader"))])
def list_triggers(request: Request):
    tenant_id = resolve_tenant(request)
    store: dict[str, dict[str, Any]] = request.app.state.headless_triggers
    triggers = [item for item in store.values() if item.get("tenant_id") == tenant_id]
    return JSONResponse(content={"items": triggers})


@router.delete("/triggers/{trigger_id}", dependencies=[Depends(require_role("admin"))])
def delete_trigger(request: Request, trigger_id: str):
    _ensure_write_allowed(request)
    tenant_id = resolve_tenant(request)
    store: dict[str, dict[str, Any]] = request.app.state.headless_triggers
    current = store.get(trigger_id)
    if not current or current.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Trigger not found")

    removed = store.pop(trigger_id)
    _persist_triggers(request)
    event_id = request.app.state.reliable_delivery.emit("triggers/delete", removed)
    return JSONResponse(content={"success": True, "event_id": event_id})


@router.post("/cameras/{camera_id}/regions/upsert", dependencies=[Depends(require_role("admin"))])
def upsert_region(request: Request, camera_id: str, body: RegionModel):
    _ensure_write_allowed(request)
    tenant_id = resolve_tenant(request, body.tenant_id)
    if tenant_id != body.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    if camera_id != body.camera_id:
        raise HTTPException(status_code=400, detail="camera_id mismatch")

    region_store: dict[str, dict[str, Any]] = request.app.state.headless_regions
    region = body.model_dump(mode="json")
    region_store[f"{tenant_id}:{camera_id}:{body.id}"] = region
    _persist_regions(request)

    # Optional hot reload: if polygon, map region to zone coordinates.
    if camera_id in request.app.frigate_config.cameras and body.shape.type == "polygon" and body.shape.points:
        zone_name = body.metadata.get("name", body.id)
        zone_config = {
            "coordinates": ",".join([f"{p[0]},{p[1]}" for p in body.shape.points]),
            "objects": body.metadata.get("labels", []),
            "inertia": body.metadata.get("inertia", 3),
            "loitering_time": body.metadata.get("loitering_time", 0),
        }
        zones = request.app.frigate_config.cameras[camera_id].zones
        zones[zone_name] = zone_config
        request.app.config_publisher.publish_update(
            CameraConfigUpdateTopic(CameraConfigUpdateEnum.zones, camera_id),
            zones,
        )

    event_id = request.app.state.reliable_delivery.emit("regions/upsert", region)
    return JSONResponse(content={"success": True, "region": region, "event_id": event_id})


@router.get("/cameras/{camera_id}/regions", dependencies=[Depends(require_role("reader"))])
def list_regions(request: Request, camera_id: str):
    tenant_id = resolve_tenant(request)
    region_store: dict[str, dict[str, Any]] = request.app.state.headless_regions
    regions = [
        item
        for item in region_store.values()
        if item.get("tenant_id") == tenant_id and item.get("camera_id") == camera_id
    ]
    return JSONResponse(content={"items": regions})


@router.delete("/cameras/{camera_id}/regions/{region_id}", dependencies=[Depends(require_role("admin"))])
def delete_region(request: Request, camera_id: str, region_id: str):
    _ensure_write_allowed(request)
    tenant_id = resolve_tenant(request)
    region_store: dict[str, dict[str, Any]] = request.app.state.headless_regions
    key = f"{tenant_id}:{camera_id}:{region_id}"
    if key not in region_store:
        raise HTTPException(status_code=404, detail="Region not found")

    removed = region_store.pop(key)
    _persist_regions(request)
    event_id = request.app.state.reliable_delivery.emit("regions/delete", removed)
    return JSONResponse(content={"success": True, "event_id": event_id})


@router.get("/events/stream", dependencies=[Depends(require_role("reader"))])
def events_stream(request: Request):
    sse_client = request.app.state.sse_client
    stream_queue: queue.Queue = sse_client.register_stream()

    def event_gen():
        try:
            while True:
                try:
                    item = stream_queue.get(timeout=15)
                except queue.Empty:
                    yield "event: heartbeat\\ndata: {}\\n\\n"
                    continue

                if item is None:
                    break

                payload = json.dumps(item, default=str)
                yield f"event: message\\ndata: {payload}\\n\\n"
        finally:
            sse_client.unregister_stream(stream_queue)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.get("/events/delivery/status", dependencies=[Depends(require_role("reader"))])
def events_delivery_status(request: Request):
    return JSONResponse(content=request.app.state.reliable_delivery.snapshot())


@router.get("/noise/suggestions", dependencies=[Depends(require_role("reader"))])
def noise_suggestions(request: Request):
    tenant_id = resolve_tenant(request)
    stats = request.app.stats_emitter.get_latest_stats()
    effective = request.app.state.runtime_config_store.effective_dict()
    items = generate_noise_suggestions(stats, effective, tenant_id)

    store: dict[str, dict[str, Any]] = request.app.state.headless_noise_suggestions
    store.clear()
    for item in items:
        store[item["id"]] = item

    return JSONResponse(content={"items": items})


@router.post(
    "/noise/suggestions/{suggestion_id}/approve",
    dependencies=[Depends(require_role("admin"))],
)
def noise_suggestion_approve(
    request: Request, suggestion_id: str, body: SuggestionApproveRequest
):
    _ensure_write_allowed(request)
    tenant_id = resolve_tenant(request, body.tenant_id)
    store: dict[str, dict[str, Any]] = request.app.state.headless_noise_suggestions
    suggestion = store.get(suggestion_id)
    if not suggestion or suggestion.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    if body.auto_approve and suggestion.get("risk") != "low":
        raise HTTPException(
            status_code=403,
            detail="Auto-approval is restricted to low-risk suggestions",
        )

    patch = suggestion.get("patch")
    if not patch:
        raise HTTPException(
            status_code=422,
            detail="Suggestion requires manual geometry/patch before applying",
        )

    runtime_store = request.app.state.runtime_config_store
    before = runtime_store.effective_dict()

    try:
        runtime_store.apply_runtime_patch(patch)
        _persist_runtime_overlay(request, tenant_id)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    after = runtime_store.effective_dict()
    changed = diff_top_level_keys(before, after)
    restart_needed = requires_restart(changed)
    _apply_zones_hot_reload(request, patch)

    audit_entry = {
        "suggestion_id": suggestion_id,
        "tenant_id": tenant_id,
        "applied_at": int(time.time()),
        "auto_approve": body.auto_approve,
        "changes": changed,
        "requires_restart": restart_needed,
    }
    request.app.state.headless_noise_audit.append(audit_entry)
    append_audit_entry(
        request.app.state.headless_governance,
        {
            "ts": int(time.time()),
            "period": current_period(),
            "origin": "manual" if not body.auto_approve else "automatic",
            "action": "apply",
            "source": "noise_suggestion",
            "suggestion_id": suggestion_id,
            "changes": changed,
            "requires_restart": restart_needed,
        },
    )
    suggestion["status"] = "applied"

    return JSONResponse(
        content={
            "success": True,
            "requires_restart": restart_needed,
            "changes": changed,
            "audit": audit_entry,
        }
    )


@router.get("/noise/audit", dependencies=[Depends(require_role("reader"))])
def noise_audit(request: Request):
    tenant_id = resolve_tenant(request)
    entries: list[dict[str, Any]] = request.app.state.headless_noise_audit
    filtered = [entry for entry in entries if entry.get("tenant_id") == tenant_id]
    return JSONResponse(content={"items": filtered})


@router.get("/optimization/loop/status", dependencies=[Depends(require_role("reader"))])
def optimization_loop_status(request: Request):
    stats = request.app.stats_emitter.get_latest_stats()
    runtime_store = request.app.state.runtime_config_store
    canary = runtime_store.evaluate_canary(stats, time.time())
    loop_state: dict[str, Any] = request.app.state.headless_closed_loop
    return JSONResponse(
        content={
            "enabled": bool(loop_state.get("enabled", True)),
            "observation_interval_sec": int(loop_state.get("observation_interval_sec", 180)),
            "freeze_until_ts": int(loop_state.get("freeze_until_ts", 0.0)),
            "last_decision": loop_state.get("last_decision", {}),
            "history": loop_state.get("history", []),
            "canary": canary,
        }
    )


@router.post("/optimization/loop/control", dependencies=[Depends(require_role("admin"))])
def optimization_loop_control(request: Request, body: ClosedLoopControlRequest):
    _ensure_write_allowed(request)
    resolve_tenant(request)
    state: dict[str, Any] = request.app.state.headless_closed_loop
    if body.enabled is not None:
        state["enabled"] = body.enabled
    if body.observation_interval_sec is not None:
        state["observation_interval_sec"] = body.observation_interval_sec
    if body.freeze_sec is not None:
        state["freeze_until_ts"] = time.time() + body.freeze_sec

    return JSONResponse(
        content={
            "enabled": bool(state.get("enabled", True)),
            "observation_interval_sec": int(state.get("observation_interval_sec", 180)),
            "freeze_until_ts": int(state.get("freeze_until_ts", 0.0)),
        }
    )


@router.get("/governance/policy", dependencies=[Depends(require_role("reader"))])
def governance_policy(request: Request):
    return JSONResponse(content=request.app.state.headless_governance)


@router.post("/governance/policy", dependencies=[Depends(require_role("admin"))])
def governance_policy_update(request: Request, body: GovernancePolicyRequest):
    _ensure_write_allowed(request)
    resolve_tenant(request)
    state: dict[str, Any] = request.app.state.headless_governance
    if body.policy_version is not None:
        state["policy_version"] = body.policy_version
    if body.owner is not None:
        state["owner"] = body.owner
    if body.approval_mode is not None:
        state["approval_mode"] = body.approval_mode
    if body.technical_committee is not None:
        state["technical_committee"] = body.technical_committee
    return JSONResponse(content=state)


@router.get("/governance/audit", dependencies=[Depends(require_role("reader"))])
def governance_audit(request: Request):
    state: dict[str, Any] = request.app.state.headless_governance
    return JSONResponse(content={"items": state.get("audit_entries", [])})


@router.get(
    "/governance/recalibration/schedule", dependencies=[Depends(require_role("reader"))]
)
def governance_recalibration_schedule(request: Request):
    state: dict[str, Any] = request.app.state.headless_governance
    return JSONResponse(content={"items": state.get("recalibration_schedule", {})})


@router.post(
    "/governance/recalibration/schedule", dependencies=[Depends(require_role("admin"))]
)
def governance_recalibration_schedule_upsert(
    request: Request, body: RecalibrationScheduleRequest
):
    _ensure_write_allowed(request)
    resolve_tenant(request)
    state: dict[str, Any] = request.app.state.headless_governance
    schedule: dict[str, Any] = state.setdefault("recalibration_schedule", {})
    schedule[body.segment] = body.model_dump(mode="json")
    return JSONResponse(content={"success": True, "item": schedule[body.segment]})


@router.get("/governance/scorecard", dependencies=[Depends(require_role("reader"))])
def governance_scorecard(request: Request, period: str | None = None):
    stats = request.app.stats_emitter.get_latest_stats()
    gov_state: dict[str, Any] = request.app.state.headless_governance
    use_period = period or current_period()
    scorecard = build_monthly_scorecard(
        stats, gov_state.get("audit_entries", []), use_period
    )
    return JSONResponse(content=scorecard)


@router.get("/security/audit", dependencies=[Depends(require_role("reader"))])
def security_audit(request: Request, limit: int = 100):
    entries: list[dict[str, Any]] = request.app.state.headless_security_audit
    db_entries = request.app.state.headless_db_adapter.list_audit("security", limit=limit)
    if db_entries:
        entries = db_entries
    safe_limit = max(1, min(500, int(limit)))
    return JSONResponse(content={"items": entries[-safe_limit:]})


@router.post("/resilience/chaos/inject", dependencies=[Depends(require_role("admin"))])
def resilience_chaos_inject(request: Request, body: ChaosInjectionRequest):
    _ensure_write_allowed(request)
    resolve_tenant(request)
    state: dict[str, Any] = request.app.state.headless_self_healing
    event = register_chaos_event(state, body.scenario)

    if body.scenario == "delivery_worker_restart":
        request.app.state.reliable_delivery.process_due()
    elif body.scenario == "simulate_webhook_failure":
        request.app.state.reliable_delivery.emit(
            "chaos/webhook",
            {"scenario": body.scenario, "ts": int(time.time())},
            event_id=f"chaos-{int(time.time())}",
        )
    elif body.scenario == "simulate_backpressure":
        request.app.state.storage_sync.enqueue_replication(
            tenant_id="default",
            key=f"chaos/backpressure-{int(time.time())}.json",
            payload={"scenario": body.scenario},
        )

    _self_heal_if_needed(request, reason=f"chaos:{body.scenario}")
    return JSONResponse(content={"success": True, "event": event, "self_healing": state})


@router.get("/resilience/self-healing/status", dependencies=[Depends(require_role("reader"))])
def resilience_self_healing_status(request: Request):
    return JSONResponse(content=request.app.state.headless_self_healing)


@router.get("/resilience/observability/slo", dependencies=[Depends(require_role("reader"))])
def resilience_observability_slo(request: Request):
    readiness = _compute_readiness(request)
    snapshot = build_observability_snapshot(
        readiness=readiness,
        delivery_status=request.app.state.reliable_delivery.snapshot(),
        rate_limit_audit=request.app.state.headless_security_audit,
        storage_sync=request.app.state.storage_sync.status(),
    )
    return JSONResponse(content=snapshot)


@router.get("/resilience/release-gate", dependencies=[Depends(require_role("reader"))])
def resilience_release_gate(request: Request):
    readiness = _compute_readiness(request)
    snapshot = build_observability_snapshot(
        readiness=readiness,
        delivery_status=request.app.state.reliable_delivery.snapshot(),
        rate_limit_audit=request.app.state.headless_security_audit,
        storage_sync=request.app.state.storage_sync.status(),
    )
    return JSONResponse(content=evaluate_release_gate(snapshot))


@router.post("/resilience/storage/config", dependencies=[Depends(require_role("admin"))])
def resilience_storage_config(request: Request, body: StorageConfigRequest):
    _ensure_write_allowed(request)
    tenant_id = resolve_tenant(request, body.tenant_id)
    item = request.app.state.storage_sync.update_storage_config(
        tenant_id,
        {
            "provider": body.provider,
            "bucket": body.bucket,
            "region": body.region,
            "endpoint": body.endpoint,
            "prefix": body.prefix,
        },
    )
    return JSONResponse(content={"success": True, "item": item})


@router.get("/resilience/storage/sync/status", dependencies=[Depends(require_role("reader"))])
def resilience_storage_sync_status(request: Request):
    return JSONResponse(content=request.app.state.storage_sync.status())


@ops_router.get("/healthz")
def healthz():
    return JSONResponse(content={"status": "ok"})


@ops_router.get("/readyz")
def readyz(request: Request):
    readiness = _compute_readiness(request)
    payload = {
        "ready": readiness.get("ready", False),
        "mode": readiness.get("mode", "not_ready"),
        "write_critical_allowed": readiness.get("write_critical_allowed", False),
        "reasons": readiness.get("reasons", []),
        "warnings": readiness.get("warnings", []),
        "checks": readiness.get("checks", {}),
        "cameras": len(request.app.frigate_config.cameras),
        "detectors": len(request.app.frigate_config.detectors),
    }
    if readiness.get("ready"):
        return JSONResponse(content=payload, status_code=200)
    return JSONResponse(content=payload, status_code=503)


@ops_router.get("/metrics", dependencies=[Depends(require_role("reader"))])
def metrics(request: Request):
    if not request.app.state.headless_settings.metrics_enabled:
        raise HTTPException(status_code=404, detail="Metrics disabled")

    stats = request.app.stats_emitter.get_latest_stats()
    update_metrics(stats=stats, event_counts=[])
    content, content_type = get_metrics()
    return Response(content=content, media_type=content_type)
