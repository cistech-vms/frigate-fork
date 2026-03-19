"""Headless runtime API for Frigate core engine."""

import copy
import json
import logging
import os
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
    camera_patch_update_types,
    deep_merge,
    diff_top_level_keys,
    patch_requires_restart,
)
from frigate.headless.installer import (
    build_camera_connection_patch,
    build_hardware_profile,
    discover_camera_candidates,
)
from frigate.headless.noise_intelligence import generate_noise_suggestions
from frigate.headless.observability import (
    build_observability_snapshot,
    evaluate_release_gate,
)
from frigate.headless.production_readiness import build_production_readiness_report
from frigate.headless.backup_restore import BackupRestoreManager
from frigate.headless.contracts import validate_contract_compatibility, with_contract_metadata
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


def _candidate_camera_payload(candidate_camera: Any, update_type: str) -> Any:
    if update_type == "audio":
        return candidate_camera.audio
    if update_type == "audio_transcription":
        return candidate_camera.audio_transcription
    if update_type == "birdseye":
        return candidate_camera.birdseye
    if update_type == "detect":
        return candidate_camera.detect
    if update_type == "enabled":
        return candidate_camera.enabled
    if update_type == "motion":
        return candidate_camera.motion
    if update_type == "notifications":
        return candidate_camera.notifications
    if update_type == "objects":
        return candidate_camera.objects
    if update_type == "object_genai":
        return candidate_camera.objects.genai
    if update_type == "record":
        return candidate_camera.record
    if update_type == "review":
        return candidate_camera.review
    if update_type == "review_genai":
        return candidate_camera.review.genai
    if update_type == "semantic_search":
        return candidate_camera.semantic_search
    if update_type == "snapshots":
        return candidate_camera.snapshots
    if update_type == "zones":
        return candidate_camera.zones
    raise ValueError(f"Unsupported camera hot reload topic: {update_type}")


def _apply_camera_payload(current_camera: Any, candidate_camera: Any, update_type: str) -> None:
    if update_type == "audio":
        current_camera.audio = candidate_camera.audio
    elif update_type == "audio_transcription":
        current_camera.audio_transcription = candidate_camera.audio_transcription
    elif update_type == "birdseye":
        current_camera.birdseye = candidate_camera.birdseye
    elif update_type == "detect":
        current_camera.detect = candidate_camera.detect
    elif update_type == "enabled":
        current_camera.enabled = candidate_camera.enabled
    elif update_type == "motion":
        current_camera.motion = candidate_camera.motion
    elif update_type == "notifications":
        current_camera.notifications = candidate_camera.notifications
    elif update_type == "objects":
        current_camera.objects = candidate_camera.objects
    elif update_type == "object_genai":
        current_camera.objects.genai = candidate_camera.objects.genai
    elif update_type == "record":
        current_camera.record = candidate_camera.record
    elif update_type == "review":
        current_camera.review = candidate_camera.review
    elif update_type == "review_genai":
        current_camera.review.genai = candidate_camera.review.genai
    elif update_type == "semantic_search":
        current_camera.semantic_search = candidate_camera.semantic_search
    elif update_type == "snapshots":
        current_camera.snapshots = candidate_camera.snapshots
    elif update_type == "zones":
        current_camera.zones = candidate_camera.zones
    else:
        raise ValueError(f"Unsupported camera hot reload topic: {update_type}")


def apply_runtime_hot_reload(app: Any, patch: dict[str, Any], candidate_config: Any) -> list[str]:
    if not isinstance(patch, dict) or candidate_config is None:
        return []

    cameras_patch = patch.get("cameras", {})
    if not isinstance(cameras_patch, dict):
        return []

    applied: list[str] = []

    for camera_name, camera_patch in cameras_patch.items():
        if not isinstance(camera_patch, dict):
            continue

        if camera_name not in app.frigate_config.cameras:
            continue

        candidate_camera = candidate_config.cameras.get(camera_name)
        if candidate_camera is None:
            continue

        current_camera = app.frigate_config.cameras[camera_name]
        for update_type in sorted(camera_patch_update_types(camera_patch)):
            _apply_camera_payload(current_camera, candidate_camera, update_type)
            app.config_publisher.publish_update(
                CameraConfigUpdateTopic(
                    CameraConfigUpdateEnum[update_type],
                    camera_name,
                ),
                _candidate_camera_payload(candidate_camera, update_type),
            )
            applied.append(f"{camera_name}:{update_type}")

    return applied


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


class BackupCreateRequest(BaseModel):
    name: str = "runtime"
    mode: Literal["incremental", "full"] = "incremental"
    include_runtime_state: bool = True
    include_rate_limit_state: bool = True


class BackupRestoreRequest(BaseModel):
    backup_id: str
    restore_runtime_state: bool = True
    restore_rate_limit_state: bool = True


class SecretRotateRequest(BaseModel):
    name: str
    value: str


class ContractValidationRequest(BaseModel):
    requested_api_version: str | None = None


class MigrationApplyRequest(BaseModel):
    target_version: int = Field(ge=1)
    backup_id: str | None = None


class IdempotencyCheckRequest(BaseModel):
    tenant_id: str | None = None
    request_key: str
    payload: dict[str, Any] = Field(default_factory=dict)


class DrExerciseRequest(BaseModel):
    scenario: str
    rpo_sec: int = Field(default=300, ge=0)
    rto_sec: int = Field(default=900, ge=0)
    success: bool = True


class QuotaSetRequest(BaseModel):
    tenant_id: str
    api_write_per_min: int = Field(default=120, ge=1)
    storage_objects: int = Field(default=100000, ge=1)
    events_per_min: int = Field(default=5000, ge=1)


class QuotaConsumeRequest(BaseModel):
    tenant_id: str
    resource: Literal["api_write_per_min", "storage_objects", "events_per_min"]
    amount: int = Field(default=1, ge=1)


class SupplyChainScanRequest(BaseModel):
    vulnerabilities: list[dict[str, Any]] = Field(default_factory=list)


class SupplyChainSignRequest(BaseModel):
    image_ref: str


class LoadChaosRecordRequest(BaseModel):
    profile: str
    latency_ms: float = Field(ge=0.0)
    event_loss_pct: float = Field(ge=0.0)
    backlog: int = Field(ge=0)
    recovery_sec: int = Field(ge=0)


class InstallDiscoveryScanRequest(BaseModel):
    targets: list[str] = Field(default_factory=lambda: ["192.168.1.0/24"])
    username: str | None = None
    password: str | None = None
    rtsp_ports: list[int] = Field(default_factory=lambda: [554, 8554])
    onvif_ports: list[int] = Field(default_factory=lambda: [80, 8000, 8080, 8899])
    profiles: list[str] = Field(
        default_factory=lambda: ["hikvision", "dahua", "reolink", "uniview", "generic"]
    )
    max_hosts: int = Field(default=256, ge=1, le=4096)
    max_channels: int = Field(default=16, ge=1, le=128)
    max_candidates: int = Field(default=128, ge=1, le=1024)
    timeout_sec: float = Field(default=2.0, ge=0.5, le=15.0)


class InstallDiscoveryConnectRequest(BaseModel):
    tenant_id: str | None = None
    candidate_ids: list[str] = Field(default_factory=list)
    connect_all: bool = False
    camera_name_prefix: str = Field(default="cam", min_length=1, max_length=32)
    detect_enabled: bool = True
    record_enabled: bool = True


class ScalingPlanApplyRequest(BaseModel):
    tenant_id: str
    config_version: int = Field(ge=1)
    assigned_cameras: list[str] = Field(default_factory=list)
    request_id: str | None = None
    if_match: str | None = None


class ScalingHeartbeatRequest(BaseModel):
    tenant_id: str
    fps: float = Field(ge=0.0)
    queue_depth: int = Field(ge=0)
    inference_latency_ms: float = Field(ge=0.0)


class ScalingRebalanceRequest(BaseModel):
    tenant_id: str
    max_cameras_per_node: int = Field(default=32, ge=1, le=10000)


class ScalingStorageStrategyRequest(BaseModel):
    hot_state_backend: str = "local"
    historical_backend: str = "local"
    retention_by_tenant: dict[str, int] = Field(default_factory=dict)


class ScalingEventPublishRequest(BaseModel):
    tenant_id: str
    priority: Literal["high", "normal", "low"] = "normal"
    payload: dict[str, Any] = Field(default_factory=dict)


class ScalingCanaryRequest(BaseModel):
    tenant_id: str
    target_version: int = Field(ge=1)
    cameras: list[str] = Field(default_factory=list)


class ScalingCanaryFinalizeRequest(BaseModel):
    tenant_id: str
    promote: bool = True


class OptimizationBaselineRequest(BaseModel):
    tier: Literal["edge_basic", "edge_medium", "edge_robust"]
    profile: dict[str, Any] = Field(default_factory=dict)


class OptimizationTargetsRequest(BaseModel):
    inference_latency_p95_ms: float | None = Field(default=None, ge=1.0)
    queue_depth_max: float | None = Field(default=None, ge=1.0)
    drop_rate_max_pct: float | None = Field(default=None, ge=0.0)
    event_delivery_latency_p95_ms: float | None = Field(default=None, ge=1.0)


class OptimizationTenantConfigRequest(BaseModel):
    tenant_id: str
    config: dict[str, Any] = Field(default_factory=dict)


class OptimizationQueueRequest(BaseModel):
    priority: Literal["critical", "normal", "best_effort"] = "normal"
    amount: int = Field(default=1, ge=1, le=100000)


class OptimizationDeliveryEfficiencyRequest(BaseModel):
    ttl_by_criticality: dict[str, int] | None = None
    compression_profile: str | None = None
    retry_max_attempts: int | None = Field(default=None, ge=1, le=20)
    retry_backoff_base_sec: float | None = Field(default=None, ge=0.1, le=120.0)


class OptimizationBenchmarkRequest(BaseModel):
    cameras: int = Field(ge=1, le=10000)
    inference_p95_ms: float = Field(ge=0.0)
    event_delivery_p95_ms: float = Field(ge=0.0)
    drop_rate_pct: float = Field(ge=0.0)
    queue_depth: int = Field(ge=0)
    chaos_scenario: str | None = None


class AdaptiveSegmentClassifyRequest(BaseModel):
    camera_id: str
    segment: Literal["indoor", "outdoor", "baixa_luz", "alto_movimento", "unclassified"]


class AdaptiveSegmentLimitsRequest(BaseModel):
    segment: Literal["indoor", "outdoor", "baixa_luz", "alto_movimento", "unclassified"]
    limits: dict[str, float] = Field(default_factory=dict)


class AdaptiveDayNightProfileRequest(BaseModel):
    camera_id: str
    day_profile: dict[str, Any] = Field(default_factory=dict)
    night_profile: dict[str, Any] = Field(default_factory=dict)
    day_start: str = "06:00"
    night_start: str = "18:00"


class AdaptiveDayNightEvaluateRequest(BaseModel):
    camera_id: str
    now_hhmm: str | None = None


class AdaptiveRuleUpsertRequest(BaseModel):
    camera_id: str
    label: str
    min_threshold: float = Field(ge=0.0, le=1.0)
    max_threshold: float = Field(ge=0.0, le=1.0)
    min_cooldown: int = Field(ge=0, le=3600)
    max_cooldown: int = Field(ge=0, le=3600)
    current_threshold: float = Field(ge=0.0, le=1.0)
    current_cooldown: int = Field(ge=0, le=3600)


class AdaptiveRuleEvaluateRequest(BaseModel):
    camera_id: str
    label: str
    repeat_rate: float = Field(ge=0.0)
    is_critical: bool = False


class CmsSyncRequest(BaseModel):
    force: bool = True


def _runtime_tenant(request: Request, tenant_id: str | None = None) -> str:
    if tenant_id:
        request.app.state.headless_runtime_tenant = tenant_id
        return tenant_id
    return str(getattr(request.app.state, "headless_runtime_tenant", "default"))


def _ensure_installer_enabled(request: Request) -> None:
    settings = request.app.state.headless_settings
    if not getattr(settings, "installer_enabled", True):
        raise HTTPException(status_code=404, detail="Installer mode disabled")
    if len(request.app.frigate_config.cameras) > 0:
        raise HTTPException(
            status_code=403,
            detail="Installer assistant is only available before cameras are configured",
        )


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
    cms_remote = getattr(request.app.state, "headless_cms_remote", None)
    if cms_remote is not None:
        snapshot = cms_remote.enrich_readiness(snapshot)
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


def _check_contract_header(request: Request) -> None:
    requested = request.headers.get("x-api-contract-version")
    ok, reason = validate_contract_compatibility(requested)
    if not ok:
        raise HTTPException(
            status_code=426,
            detail={"error": "Unsupported API contract version", "reason": reason},
        )


def _check_idempotency(request: Request, tenant_id: str, payload: Any) -> None:
    key = request.headers.get("x-idempotency-key")
    if not key:
        return
    duplicated, item = request.app.state.headless_idempotency.record_or_get(
        tenant_id=tenant_id,
        request_key=key,
        payload=payload,
    )
    if duplicated:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Duplicated idempotent request",
                "reason": "idempotency_key_reused",
                "recorded_at": item.get("recorded_at"),
            },
        )


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
    _check_contract_header(request)
    tenant_id = resolve_tenant(request, body.tenant_id)
    _check_idempotency(request, tenant_id, body.model_dump(mode="json"))
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
    _check_contract_header(request)
    tenant_id = resolve_tenant(request, body.tenant_id)
    _check_idempotency(request, tenant_id, body.model_dump(mode="json"))
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
            candidate_config, applied_patch, canary_status = store.start_canary(
                body.config, policy, latest_stats, time.time()
            )
            apply_runtime_hot_reload(request.app, applied_patch, candidate_config)
            _persist_runtime_overlay(request, active_tenant)
            after = store.effective_dict()
            changed = diff_top_level_keys(before, after)
            restart_needed = patch_requires_restart(applied_patch, changed)
            return JSONResponse(
                content={
                    "requires_restart": restart_needed,
                    "changes": changed,
                    "message": "Canary rollout started",
                    "canary": canary_status,
                }
            )
        candidate_config = store.apply_runtime_patch(body.config)
        _persist_runtime_overlay(request, active_tenant)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    after = store.effective_dict()
    changed = diff_top_level_keys(before, after)
    restart_needed = patch_requires_restart(body.config, changed)
    apply_runtime_hot_reload(request.app, body.config, candidate_config)
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
    _check_contract_header(request)
    tenant_id = resolve_tenant(request, body.tenant_id)
    _check_idempotency(request, tenant_id, body.model_dump(mode="json"))
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
    _check_contract_header(request)
    tenant_id = resolve_tenant(request, body.tenant_id)
    _check_idempotency(request, tenant_id, body.model_dump(mode="json"))
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
    _check_contract_header(request)
    tenant_id = resolve_tenant(request, body.tenant_id)
    _check_idempotency(
        request,
        tenant_id,
        {"suggestion_id": suggestion_id, **body.model_dump(mode="json")},
    )
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
        candidate_config = runtime_store.apply_runtime_patch(patch)
        _persist_runtime_overlay(request, tenant_id)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    after = runtime_store.effective_dict()
    changed = diff_top_level_keys(before, after)
    restart_needed = patch_requires_restart(patch, changed)
    apply_runtime_hot_reload(request.app, patch, candidate_config)

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


@router.get("/production/readiness", dependencies=[Depends(require_role("reader"))])
def production_readiness_report(request: Request):
    readiness = _compute_readiness(request)
    delivery_status = request.app.state.reliable_delivery.snapshot()
    storage_sync = request.app.state.storage_sync.status()
    snapshot = build_observability_snapshot(
        readiness=readiness,
        delivery_status=delivery_status,
        rate_limit_audit=request.app.state.headless_security_audit,
        storage_sync=storage_sync,
    )
    release_gate = evaluate_release_gate(snapshot)
    context = {
        "env": dict(os.environ),
        "settings": request.app.state.headless_settings.__dict__,
        "readiness": readiness,
        "release_gate": release_gate,
        "migrations": request.app.state.headless_migrations.snapshot(),
        "secrets": request.app.state.headless_secret_rotation.snapshot(),
        "delivery": delivery_status,
        "storage_sync": storage_sync,
        "dr": request.app.state.headless_dr.snapshot(),
        "backups": BackupRestoreManager().list_backups(limit=30),
        "optimization_gate": request.app.state.headless_optimization.benchmark_gate(),
        "optimization": request.app.state.headless_optimization.snapshot(),
        "runbooks": request.app.state.headless_runbooks,
        "governance": request.app.state.headless_governance,
        "load_chaos_summary": request.app.state.headless_load_chaos.summary(),
        "scaling_state": request.app.state.headless_horizontal_scaling.state,
        "rate_limiter": {"configured": request.app.state.headless_rate_limiter is not None},
        "redis_enabled": request.app.state.headless_redis_adapter is not None,
        "contract_compatibility_checked": bool(
            request.app.state.headless_governance.get("audit_entries")
        ),
        "oncall_drill_completed": bool(request.app.state.headless_dr.snapshot().get("exercises")),
        "supply_chain": request.app.state.headless_supply_chain.snapshot(),
        "cms_status": request.app.state.headless_cms_remote.status(),
    }
    return JSONResponse(content=build_production_readiness_report(context))


@router.get("/cms/status", dependencies=[Depends(require_role("reader"))])
def cms_status(request: Request):
    manager = getattr(request.app.state, "headless_cms_remote", None)
    if manager is None:
        return JSONResponse(content={"enabled": False, "mode": "not_initialized"})
    return JSONResponse(content=manager.status())


@router.post("/cms/sync", dependencies=[Depends(require_role("admin"))])
def cms_sync(request: Request, body: CmsSyncRequest):
    manager = getattr(request.app.state, "headless_cms_remote", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="CMS remote manager not initialized")
    snapshot = manager.sync_once(force=body.force, reason="api")
    return JSONResponse(content={"success": True, "status": snapshot})


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


@router.post("/resilience/backup/create", dependencies=[Depends(require_role("admin"))])
def resilience_backup_create(request: Request, body: BackupCreateRequest):
    _ensure_write_allowed(request)
    _check_contract_header(request)
    manager = BackupRestoreManager()
    sources: dict[str, str] = {}
    if body.include_runtime_state:
        sources["headless_state"] = request.app.state.headless_state_store.path
    if body.include_rate_limit_state:
        sources["rate_limit_state"] = request.app.state.headless_rate_limiter.state_path
    item = manager.create_backup(name=body.name, sources=sources, mode=body.mode)
    return JSONResponse(content=with_contract_metadata({"success": True, "item": item}))


@router.get("/resilience/backup/list", dependencies=[Depends(require_role("reader"))])
def resilience_backup_list(request: Request, limit: int = 30):
    manager = BackupRestoreManager()
    return JSONResponse(content={"items": manager.list_backups(limit=limit)})


@router.post("/resilience/backup/restore", dependencies=[Depends(require_role("admin"))])
def resilience_backup_restore(request: Request, body: BackupRestoreRequest):
    _ensure_write_allowed(request)
    _check_contract_header(request)
    manager = BackupRestoreManager()
    targets: dict[str, str] = {}
    if body.restore_runtime_state:
        targets["headless_state"] = request.app.state.headless_state_store.path
    if body.restore_rate_limit_state:
        targets["rate_limit_state"] = request.app.state.headless_rate_limiter.state_path
    item = manager.restore_backup(body.backup_id, targets)
    return JSONResponse(content=with_contract_metadata({"success": True, "item": item}))


@router.post("/resilience/secrets/rotate", dependencies=[Depends(require_role("admin"))])
def resilience_secrets_rotate(request: Request, body: SecretRotateRequest):
    _ensure_write_allowed(request)
    _check_contract_header(request)
    item = request.app.state.headless_secret_rotation.rotate(body.name, body.value)
    request.app.state.headless_db_adapter.append_audit(
        "secrets", {"event": "rotated", **item}
    )
    return JSONResponse(content={"success": True, "item": item})


@router.post("/resilience/secrets/revoke/{name}", dependencies=[Depends(require_role("admin"))])
def resilience_secrets_revoke(request: Request, name: str):
    _ensure_write_allowed(request)
    item = request.app.state.headless_secret_rotation.revoke_previous(name)
    request.app.state.headless_db_adapter.append_audit(
        "secrets", {"event": "revoked_previous", **item}
    )
    return JSONResponse(content={"success": True, "item": item})


@router.get("/resilience/secrets/status", dependencies=[Depends(require_role("reader"))])
def resilience_secrets_status(request: Request):
    return JSONResponse(content=request.app.state.headless_secret_rotation.snapshot())


@router.post("/resilience/contracts/validate", dependencies=[Depends(require_role("reader"))])
def resilience_contract_validate(request: Request, body: ContractValidationRequest):
    ok, reason = validate_contract_compatibility(body.requested_api_version)
    code = 200 if ok else 426
    return JSONResponse(content={"compatible": ok, "reason": reason}, status_code=code)


@router.post("/resilience/migrations/apply", dependencies=[Depends(require_role("admin"))])
def resilience_migrations_apply(request: Request, body: MigrationApplyRequest):
    _ensure_write_allowed(request)
    item = request.app.state.headless_migrations.apply(
        body.target_version, backup_id=body.backup_id
    )
    request.app.state.headless_db_adapter.append_audit(
        "migrations", {"event": "apply", **item}
    )
    return JSONResponse(content={"success": True, "item": item})


@router.post("/resilience/migrations/rollback", dependencies=[Depends(require_role("admin"))])
def resilience_migrations_rollback(request: Request, body: MigrationApplyRequest):
    _ensure_write_allowed(request)
    item = request.app.state.headless_migrations.rollback(body.target_version)
    request.app.state.headless_db_adapter.append_audit(
        "migrations", {"event": "rollback", **item}
    )
    return JSONResponse(content={"success": True, "item": item})


@router.get("/resilience/migrations/status", dependencies=[Depends(require_role("reader"))])
def resilience_migrations_status(request: Request):
    return JSONResponse(content=request.app.state.headless_migrations.snapshot())


@router.post("/resilience/idempotency/check", dependencies=[Depends(require_role("admin"))])
def resilience_idempotency_check(request: Request, body: IdempotencyCheckRequest):
    _ensure_write_allowed(request)
    tenant_id = resolve_tenant(request, body.tenant_id)
    duplicated, item = request.app.state.headless_idempotency.record_or_get(
        tenant_id=tenant_id,
        request_key=body.request_key,
        payload=body.payload,
    )
    return JSONResponse(content={"duplicated": duplicated, "item": item})


@router.get("/resilience/idempotency/status", dependencies=[Depends(require_role("reader"))])
def resilience_idempotency_status(request: Request, limit: int = 100):
    return JSONResponse(content={"items": request.app.state.headless_idempotency.snapshot(limit=limit)})


@router.get("/resilience/runbooks", dependencies=[Depends(require_role("reader"))])
def resilience_runbooks(request: Request):
    return JSONResponse(content={"items": request.app.state.headless_runbooks})


@router.post("/resilience/dr/exercise", dependencies=[Depends(require_role("admin"))])
def resilience_dr_exercise(request: Request, body: DrExerciseRequest):
    _ensure_write_allowed(request)
    item = request.app.state.headless_dr.record_exercise(
        scenario=body.scenario,
        rpo_sec=body.rpo_sec,
        rto_sec=body.rto_sec,
        success=body.success,
    )
    return JSONResponse(content={"success": True, "item": item})


@router.get("/resilience/dr/status", dependencies=[Depends(require_role("reader"))])
def resilience_dr_status(request: Request):
    return JSONResponse(content=request.app.state.headless_dr.snapshot())


@router.post("/resilience/quotas/set", dependencies=[Depends(require_role("admin"))])
def resilience_quotas_set(request: Request, body: QuotaSetRequest):
    _ensure_write_allowed(request)
    quota = request.app.state.headless_quotas.set_quota(
        body.tenant_id,
        {
            "api_write_per_min": body.api_write_per_min,
            "storage_objects": body.storage_objects,
            "events_per_min": body.events_per_min,
        },
    )
    return JSONResponse(content={"success": True, "quota": quota})


@router.post("/resilience/quotas/consume", dependencies=[Depends(require_role("admin"))])
def resilience_quotas_consume(request: Request, body: QuotaConsumeRequest):
    _ensure_write_allowed(request)
    allowed, item = request.app.state.headless_quotas.consume(
        body.tenant_id, body.resource, amount=body.amount
    )
    status_code = 200 if allowed else 429
    return JSONResponse(content=item, status_code=status_code)


@router.get("/resilience/quotas/status", dependencies=[Depends(require_role("reader"))])
def resilience_quotas_status(request: Request):
    return JSONResponse(content=request.app.state.headless_quotas.snapshot())


@router.post("/resilience/supply-chain/sbom", dependencies=[Depends(require_role("admin"))])
def resilience_supply_chain_sbom(request: Request):
    _ensure_write_allowed(request)
    item = request.app.state.headless_supply_chain.generate_sbom(os.getcwd())
    return JSONResponse(content={"success": True, "item": item})


@router.post("/resilience/supply-chain/scan", dependencies=[Depends(require_role("admin"))])
def resilience_supply_chain_scan(request: Request, body: SupplyChainScanRequest):
    _ensure_write_allowed(request)
    item = request.app.state.headless_supply_chain.record_scan(body.vulnerabilities)
    return JSONResponse(content={"success": True, "item": item})


@router.post("/resilience/supply-chain/sign", dependencies=[Depends(require_role("admin"))])
def resilience_supply_chain_sign(request: Request, body: SupplyChainSignRequest):
    _ensure_write_allowed(request)
    item = request.app.state.headless_supply_chain.sign_image(body.image_ref)
    return JSONResponse(content={"success": True, "item": item})


@router.get("/resilience/supply-chain/status", dependencies=[Depends(require_role("reader"))])
def resilience_supply_chain_status(request: Request):
    return JSONResponse(content=request.app.state.headless_supply_chain.snapshot())


@router.post("/resilience/load-chaos/record", dependencies=[Depends(require_role("admin"))])
def resilience_load_chaos_record(request: Request, body: LoadChaosRecordRequest):
    _ensure_write_allowed(request)
    item = request.app.state.headless_load_chaos.record(
        profile=body.profile,
        latency_ms=body.latency_ms,
        event_loss_pct=body.event_loss_pct,
        backlog=body.backlog,
        recovery_sec=body.recovery_sec,
    )
    return JSONResponse(content={"success": True, "item": item})


@router.get("/resilience/load-chaos/summary", dependencies=[Depends(require_role("reader"))])
def resilience_load_chaos_summary(request: Request):
    return JSONResponse(content=request.app.state.headless_load_chaos.summary())


@router.post("/scaling/plan/apply", dependencies=[Depends(require_role("admin"))])
def scaling_plan_apply(request: Request, body: ScalingPlanApplyRequest):
    _ensure_write_allowed(request)
    _check_contract_header(request)
    _check_idempotency(request, body.tenant_id, body.model_dump(mode="json"))
    manager = request.app.state.headless_horizontal_scaling
    try:
        item = manager.apply_plan(
            tenant_id=body.tenant_id,
            config_version=body.config_version,
            assigned_cameras=body.assigned_cameras,
            request_id=body.request_id,
            if_match=body.if_match,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JSONResponse(content=with_contract_metadata({"success": True, "item": item}))


@router.get("/scaling/reconcile/{tenant_id}", dependencies=[Depends(require_role("reader"))])
def scaling_reconcile(request: Request, tenant_id: str):
    manager = request.app.state.headless_horizontal_scaling
    return JSONResponse(content=manager.reconcile(tenant_id))


@router.post("/scaling/heartbeat", dependencies=[Depends(require_role("admin"))])
def scaling_heartbeat(request: Request, body: ScalingHeartbeatRequest):
    _ensure_write_allowed(request)
    manager = request.app.state.headless_horizontal_scaling
    item = manager.heartbeat(
        tenant_id=body.tenant_id,
        fps=body.fps,
        queue_depth=body.queue_depth,
        inference_latency_ms=body.inference_latency_ms,
    )
    return JSONResponse(content={"success": True, "item": item})


@router.get("/scaling/shards/status", dependencies=[Depends(require_role("reader"))])
def scaling_shards_status(request: Request):
    manager = request.app.state.headless_horizontal_scaling
    return JSONResponse(
        content={
            "shards": manager.state.get("shards", {}),
            "metrics": manager.shard_metrics(),
        }
    )


@router.post("/scaling/shards/rebalance", dependencies=[Depends(require_role("admin"))])
def scaling_shards_rebalance(request: Request, body: ScalingRebalanceRequest):
    _ensure_write_allowed(request)
    manager = request.app.state.headless_horizontal_scaling
    result = manager.rebalance(
        body.tenant_id, max_cameras_per_node=body.max_cameras_per_node
    )
    return JSONResponse(content={"success": True, "result": result})


@router.post("/scaling/storage/strategy", dependencies=[Depends(require_role("admin"))])
def scaling_storage_strategy(request: Request, body: ScalingStorageStrategyRequest):
    _ensure_write_allowed(request)
    manager = request.app.state.headless_horizontal_scaling
    item = manager.configure_storage_strategy(
        hot_state_backend=body.hot_state_backend,
        historical_backend=body.historical_backend,
        tenant_retention=body.retention_by_tenant,
    )
    return JSONResponse(content={"success": True, "item": item})


@router.post("/scaling/events/publish", dependencies=[Depends(require_role("admin"))])
def scaling_events_publish(request: Request, body: ScalingEventPublishRequest):
    _ensure_write_allowed(request)
    manager = request.app.state.headless_horizontal_scaling
    result = manager.publish_event(
        tenant_id=body.tenant_id, priority=body.priority, payload=body.payload
    )
    if not result.get("accepted"):
        raise HTTPException(status_code=429, detail=result)
    return JSONResponse(content={"success": True, "result": result})


@router.post("/scaling/events/process", dependencies=[Depends(require_role("admin"))])
def scaling_events_process(request: Request, max_batch: int = 200):
    _ensure_write_allowed(request)
    manager = request.app.state.headless_horizontal_scaling
    return JSONResponse(content=manager.process_event_tick(max_batch=max_batch))


@router.get("/scaling/events/status", dependencies=[Depends(require_role("reader"))])
def scaling_events_status(request: Request):
    manager = request.app.state.headless_horizontal_scaling
    return JSONResponse(content=manager.state.get("event_pipeline", {}))


@router.get("/scaling/slo", dependencies=[Depends(require_role("reader"))])
def scaling_slo(request: Request):
    manager = request.app.state.headless_horizontal_scaling
    return JSONResponse(content=manager.slo_snapshot())


@router.post("/scaling/rollout/canary/start", dependencies=[Depends(require_role("admin"))])
def scaling_rollout_canary_start(request: Request, body: ScalingCanaryRequest):
    _ensure_write_allowed(request)
    manager = request.app.state.headless_horizontal_scaling
    item = manager.start_canary(
        tenant_id=body.tenant_id,
        target_version=body.target_version,
        cameras=body.cameras,
    )
    return JSONResponse(content={"success": True, "item": item})


@router.post(
    "/scaling/rollout/canary/finalize", dependencies=[Depends(require_role("admin"))]
)
def scaling_rollout_canary_finalize(
    request: Request, body: ScalingCanaryFinalizeRequest
):
    _ensure_write_allowed(request)
    manager = request.app.state.headless_horizontal_scaling
    item = manager.finalize_canary(body.tenant_id, promote=body.promote)
    return JSONResponse(content={"success": True, "item": item})


@router.get("/scaling/rollout/status", dependencies=[Depends(require_role("reader"))])
def scaling_rollout_status(request: Request):
    manager = request.app.state.headless_horizontal_scaling
    return JSONResponse(content=manager.state.get("rollout", {}))


@router.post("/optimization/perf/baseline", dependencies=[Depends(require_role("admin"))])
def optimization_perf_baseline(request: Request, body: OptimizationBaselineRequest):
    _ensure_write_allowed(request)
    manager = request.app.state.headless_optimization
    item = manager.collect_baseline(body.tier, body.profile)
    return JSONResponse(content={"success": True, "item": item})


@router.post("/optimization/perf/targets", dependencies=[Depends(require_role("admin"))])
def optimization_perf_targets(request: Request, body: OptimizationTargetsRequest):
    _ensure_write_allowed(request)
    manager = request.app.state.headless_optimization
    targets = {k: v for k, v in body.model_dump(mode="json").items() if v is not None}
    item = manager.set_targets(targets)
    return JSONResponse(content={"success": True, "item": item})


@router.post("/optimization/perf/ingest-decode", dependencies=[Depends(require_role("admin"))])
def optimization_perf_ingest_decode(
    request: Request, body: OptimizationTenantConfigRequest
):
    _ensure_write_allowed(request)
    item = request.app.state.headless_optimization.configure_ingest_decode(
        body.tenant_id, body.config
    )
    return JSONResponse(content={"success": True, "item": item})


@router.post("/optimization/perf/inference", dependencies=[Depends(require_role("admin"))])
def optimization_perf_inference(request: Request, body: OptimizationTenantConfigRequest):
    _ensure_write_allowed(request)
    item = request.app.state.headless_optimization.configure_inference(
        body.tenant_id, body.config
    )
    return JSONResponse(content={"success": True, "item": item})


@router.post("/optimization/perf/tracking-regions", dependencies=[Depends(require_role("admin"))])
def optimization_perf_tracking_regions(
    request: Request, body: OptimizationTenantConfigRequest
):
    _ensure_write_allowed(request)
    item = request.app.state.headless_optimization.configure_tracking_regions(
        body.tenant_id, body.config
    )
    return JSONResponse(content={"success": True, "item": item})


@router.post("/optimization/perf/event-rules", dependencies=[Depends(require_role("admin"))])
def optimization_perf_event_rules(request: Request, body: OptimizationTenantConfigRequest):
    _ensure_write_allowed(request)
    item = request.app.state.headless_optimization.configure_event_rules(
        body.tenant_id, body.config
    )
    return JSONResponse(content={"success": True, "item": item})


@router.post("/optimization/perf/queues/enqueue", dependencies=[Depends(require_role("admin"))])
def optimization_perf_queues_enqueue(request: Request, body: OptimizationQueueRequest):
    _ensure_write_allowed(request)
    result = request.app.state.headless_optimization.enqueue(
        body.priority, amount=body.amount
    )
    if not result.get("accepted"):
        raise HTTPException(status_code=429, detail=result)
    return JSONResponse(content={"success": True, "result": result})


@router.post("/optimization/perf/queues/process", dependencies=[Depends(require_role("admin"))])
def optimization_perf_queues_process(request: Request, amount: int = 200):
    _ensure_write_allowed(request)
    return JSONResponse(content=request.app.state.headless_optimization.process_queue(amount=amount))


@router.post("/optimization/perf/delivery-efficiency", dependencies=[Depends(require_role("admin"))])
def optimization_perf_delivery_efficiency(
    request: Request, body: OptimizationDeliveryEfficiencyRequest
):
    _ensure_write_allowed(request)
    config = {k: v for k, v in body.model_dump(mode="json").items() if v is not None}
    item = request.app.state.headless_optimization.configure_delivery_efficiency(config)
    return JSONResponse(content={"success": True, "item": item})


@router.post("/optimization/perf/benchmark", dependencies=[Depends(require_role("admin"))])
def optimization_perf_benchmark(request: Request, body: OptimizationBenchmarkRequest):
    _ensure_write_allowed(request)
    item = request.app.state.headless_optimization.record_benchmark(
        cameras=body.cameras,
        inference_p95_ms=body.inference_p95_ms,
        event_delivery_p95_ms=body.event_delivery_p95_ms,
        drop_rate_pct=body.drop_rate_pct,
        queue_depth=body.queue_depth,
        chaos_scenario=body.chaos_scenario,
    )
    return JSONResponse(content={"success": True, "item": item})


@router.get("/optimization/perf/gate", dependencies=[Depends(require_role("reader"))])
def optimization_perf_gate(request: Request):
    return JSONResponse(content=request.app.state.headless_optimization.benchmark_gate())


@router.post("/optimization/perf/weekly-report", dependencies=[Depends(require_role("admin"))])
def optimization_perf_weekly_report(request: Request):
    _ensure_write_allowed(request)
    return JSONResponse(content=request.app.state.headless_optimization.weekly_report())


@router.get("/optimization/perf/status", dependencies=[Depends(require_role("reader"))])
def optimization_perf_status(request: Request):
    return JSONResponse(content=request.app.state.headless_optimization.snapshot())


@router.post("/adaptive/segments/classify", dependencies=[Depends(require_role("admin"))])
def adaptive_segments_classify(request: Request, body: AdaptiveSegmentClassifyRequest):
    _ensure_write_allowed(request)
    item = request.app.state.headless_adaptive_tuning.classify_camera(
        body.camera_id, body.segment
    )
    return JSONResponse(content={"success": True, "item": item})


@router.post("/adaptive/segments/limits", dependencies=[Depends(require_role("admin"))])
def adaptive_segments_limits(request: Request, body: AdaptiveSegmentLimitsRequest):
    _ensure_write_allowed(request)
    item = request.app.state.headless_adaptive_tuning.set_segment_limits(
        body.segment, body.limits
    )
    return JSONResponse(content={"success": True, "item": item})


@router.post("/adaptive/segments/baseline/capture", dependencies=[Depends(require_role("admin"))])
def adaptive_segments_baseline_capture(request: Request):
    _ensure_write_allowed(request)
    stats = request.app.stats_emitter.get_latest_stats()
    item = request.app.state.headless_adaptive_tuning.capture_baseline(stats)
    return JSONResponse(content={"success": True, "item": item})


@router.get("/adaptive/segments/status", dependencies=[Depends(require_role("reader"))])
def adaptive_segments_status(request: Request):
    state = request.app.state.headless_adaptive_tuning.snapshot()
    return JSONResponse(
        content={
            "segments": state.get("segments", {}),
            "baseline": state.get("segment_baseline", {}),
            "limits": state.get("segment_limits", {}),
            "health_scores": state.get("health_scores", {}),
        }
    )


@router.post("/adaptive/profiles/day-night/upsert", dependencies=[Depends(require_role("admin"))])
def adaptive_profiles_day_night_upsert(
    request: Request, body: AdaptiveDayNightProfileRequest
):
    _ensure_write_allowed(request)
    item = request.app.state.headless_adaptive_tuning.upsert_day_night_profile(
        body.camera_id,
        day_profile=body.day_profile,
        night_profile=body.night_profile,
        day_start=body.day_start,
        night_start=body.night_start,
    )
    return JSONResponse(content={"success": True, "item": item})


@router.post("/adaptive/profiles/day-night/evaluate", dependencies=[Depends(require_role("admin"))])
def adaptive_profiles_day_night_evaluate(
    request: Request, body: AdaptiveDayNightEvaluateRequest
):
    _ensure_write_allowed(request)
    try:
        item = request.app.state.headless_adaptive_tuning.evaluate_day_night(
            body.camera_id, now_hhmm=body.now_hhmm
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(content={"success": True, "item": item})


@router.post("/adaptive/rules/upsert", dependencies=[Depends(require_role("admin"))])
def adaptive_rules_upsert(request: Request, body: AdaptiveRuleUpsertRequest):
    _ensure_write_allowed(request)
    item = request.app.state.headless_adaptive_tuning.upsert_adaptive_rule(
        camera_id=body.camera_id,
        label=body.label,
        min_threshold=body.min_threshold,
        max_threshold=body.max_threshold,
        min_cooldown=body.min_cooldown,
        max_cooldown=body.max_cooldown,
        current_threshold=body.current_threshold,
        current_cooldown=body.current_cooldown,
    )
    return JSONResponse(content={"success": True, "item": item})


@router.post("/adaptive/rules/evaluate", dependencies=[Depends(require_role("admin"))])
def adaptive_rules_evaluate(request: Request, body: AdaptiveRuleEvaluateRequest):
    _ensure_write_allowed(request)
    try:
        item = request.app.state.headless_adaptive_tuning.evaluate_rule(
            body.camera_id,
            body.label,
            repeat_rate=body.repeat_rate,
            is_critical=body.is_critical,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(content={"success": True, "item": item})


@router.get("/adaptive/status", dependencies=[Depends(require_role("reader"))])
def adaptive_status(request: Request):
    return JSONResponse(content=request.app.state.headless_adaptive_tuning.snapshot())


@ops_router.get("/install/status")
def install_status(request: Request):
    _ensure_installer_enabled(request)
    installer_state = request.app.state.headless_installer
    return JSONResponse(
        content={
            "enabled": True,
            "pending_restart": bool(installer_state.get("pending_patch")),
            "cameras_configured": len(request.app.frigate_config.cameras),
            "last_scan_summary": installer_state.get("last_scan", {}).get("summary", {}),
        }
    )


@ops_router.post("/install/hardware/profile")
def install_hardware_profile(request: Request):
    _ensure_installer_enabled(request)
    profile = build_hardware_profile()
    request.app.state.headless_installer["hardware_profile"] = profile
    return JSONResponse(content=profile)


@ops_router.post("/install/discovery/scan")
def install_discovery_scan(request: Request, body: InstallDiscoveryScanRequest):
    _ensure_installer_enabled(request)
    result = discover_camera_candidates(
        ffprobe_path=request.app.frigate_config.ffmpeg.ffprobe_path,
        targets=body.targets,
        username=body.username,
        password=body.password,
        rtsp_ports=body.rtsp_ports,
        onvif_ports=body.onvif_ports,
        profiles=body.profiles,
        max_hosts=body.max_hosts,
        max_channels=body.max_channels,
        max_candidates=body.max_candidates,
        timeout_sec=body.timeout_sec,
    )
    request.app.state.headless_installer["last_scan"] = result
    return JSONResponse(content=result)


@ops_router.get("/install/discovery/candidates")
def install_discovery_candidates(request: Request):
    _ensure_installer_enabled(request)
    return JSONResponse(content=request.app.state.headless_installer.get("last_scan", {}))


@ops_router.post("/install/discovery/connect")
def install_discovery_connect(request: Request, body: InstallDiscoveryConnectRequest):
    _ensure_installer_enabled(request)
    last_scan = request.app.state.headless_installer.get("last_scan", {})
    all_candidates = last_scan.get("candidates", []) if isinstance(last_scan, dict) else []
    if not isinstance(all_candidates, list) or not all_candidates:
        raise HTTPException(status_code=409, detail="No discovery results available")

    selected_ids = set(body.candidate_ids)
    if body.connect_all:
        selected = [item for item in all_candidates if isinstance(item, dict)]
    else:
        selected = [
            item
            for item in all_candidates
            if isinstance(item, dict) and item.get("id") in selected_ids
        ]

    if not selected:
        raise HTTPException(status_code=422, detail="No discovery candidates were selected")

    store = request.app.state.runtime_config_store
    effective = store.effective_dict()
    patch = build_camera_connection_patch(
        selected_candidates=selected,
        existing_config=effective,
        camera_name_prefix=body.camera_name_prefix,
        detect_enabled=body.detect_enabled,
        record_enabled=body.record_enabled,
    )
    if not patch:
        raise HTTPException(status_code=422, detail="Unable to build camera configuration patch")

    merged_overlay = deep_merge(copy.deepcopy(store.runtime_overlay), patch)
    try:
        store.replace_runtime_overlay(merged_overlay)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    tenant = _runtime_tenant(request, body.tenant_id)
    request.app.state.headless_state_store.put_runtime_overlay(tenant, merged_overlay)
    request.app.state.headless_installer["pending_patch"] = patch

    return JSONResponse(
        content={
            "staged": True,
            "pending_restart": True,
            "message": "Cameras descobertas foram preparadas para o proximo boot do Frigate",
            "tenant_id": tenant,
            "cameras": sorted(list(patch.get("cameras", {}).keys())),
            "go2rtc_streams": sorted(
                list(patch.get("go2rtc", {}).get("streams", {}).keys())
            ),
        }
    )


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
