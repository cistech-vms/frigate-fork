"""Headless runtime API for Frigate core engine."""

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
from frigate.headless.runtime_config import diff_top_level_keys, requires_restart
from frigate.headless.security import Principal, require_role, resolve_tenant
from frigate.stats.prometheus import get_metrics, update_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["headless"])
ops_router = APIRouter(tags=["headless-ops"])


class ConfigApplyRequest(BaseModel):
    tenant_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class ConfigValidateRequest(BaseModel):
    tenant_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


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
    return JSONResponse(
        content={
            "uptime_sec": int(time.time() - request.app.state.headless_started_at),
            "version": request.app.frigate_config.version,
            "cameras": list(request.app.frigate_config.cameras.keys()),
            "stats": stats,
            "headless": True,
        }
    )


@router.get("/config/effective", dependencies=[Depends(require_role("reader"))])
def config_effective(request: Request):
    store = request.app.state.runtime_config_store
    return JSONResponse(content=store.effective_dict())


@router.post("/config/validate", dependencies=[Depends(require_role("admin"))])
def config_validate(request: Request, body: ConfigValidateRequest):
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
    tenant_id = resolve_tenant(request, body.tenant_id)
    del tenant_id

    store = request.app.state.runtime_config_store
    before = store.effective_dict()

    try:
        store.apply_runtime_patch(body.config)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    after = store.effective_dict()
    changed = diff_top_level_keys(before, after)
    restart_needed = requires_restart(changed)

    # Apply hot reload for zones only.
    cameras_patch = body.config.get("cameras", {}) if isinstance(body.config, dict) else {}
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


@router.post("/reload", dependencies=[Depends(require_role("admin"))])
def reload_supported_components(request: Request):
    # Hot reload supported here is currently limited to regions/zones and triggers.
    return JSONResponse(
        content={
            "reloaded": ["regions", "triggers"],
            "requires_restart": False,
        }
    )


@router.post("/triggers/upsert", dependencies=[Depends(require_role("admin"))])
def upsert_trigger(request: Request, body: TriggerModel):
    tenant_id = resolve_tenant(request, body.tenant_id)
    if tenant_id != body.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    store: dict[str, dict[str, Any]] = request.app.state.headless_triggers
    trigger = body.model_dump(mode="json")
    store[body.id] = trigger

    # Emit update event to stream subscribers.
    request.app.state.sse_client.publish("triggers/upsert", trigger)

    return JSONResponse(content={"success": True, "trigger": trigger})


@router.get("/triggers", dependencies=[Depends(require_role("reader"))])
def list_triggers(request: Request):
    tenant_id = resolve_tenant(request)
    store: dict[str, dict[str, Any]] = request.app.state.headless_triggers
    triggers = [item for item in store.values() if item.get("tenant_id") == tenant_id]
    return JSONResponse(content={"items": triggers})


@router.delete("/triggers/{trigger_id}", dependencies=[Depends(require_role("admin"))])
def delete_trigger(request: Request, trigger_id: str):
    tenant_id = resolve_tenant(request)
    store: dict[str, dict[str, Any]] = request.app.state.headless_triggers
    current = store.get(trigger_id)
    if not current or current.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Trigger not found")

    removed = store.pop(trigger_id)
    request.app.state.sse_client.publish("triggers/delete", removed)
    return JSONResponse(content={"success": True})


@router.post("/cameras/{camera_id}/regions/upsert", dependencies=[Depends(require_role("admin"))])
def upsert_region(request: Request, camera_id: str, body: RegionModel):
    tenant_id = resolve_tenant(request, body.tenant_id)
    if tenant_id != body.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    if camera_id != body.camera_id:
        raise HTTPException(status_code=400, detail="camera_id mismatch")

    region_store: dict[str, dict[str, Any]] = request.app.state.headless_regions
    region = body.model_dump(mode="json")
    region_store[f"{tenant_id}:{camera_id}:{body.id}"] = region

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

    request.app.state.sse_client.publish("regions/upsert", region)
    return JSONResponse(content={"success": True, "region": region})


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
    tenant_id = resolve_tenant(request)
    region_store: dict[str, dict[str, Any]] = request.app.state.headless_regions
    key = f"{tenant_id}:{camera_id}:{region_id}"
    if key not in region_store:
        raise HTTPException(status_code=404, detail="Region not found")

    removed = region_store.pop(key)
    request.app.state.sse_client.publish("regions/delete", removed)
    return JSONResponse(content={"success": True})


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


@ops_router.get("/healthz")
def healthz():
    return JSONResponse(content={"status": "ok"})


@ops_router.get("/readyz")
def readyz(request: Request):
    return JSONResponse(
        content={
            "ready": True,
            "cameras": len(request.app.frigate_config.cameras),
            "detectors": len(request.app.frigate_config.detectors),
        }
    )


@ops_router.get("/metrics", dependencies=[Depends(require_role("reader"))])
def metrics(request: Request):
    if not request.app.state.headless_settings.metrics_enabled:
        raise HTTPException(status_code=404, detail="Metrics disabled")

    stats = request.app.stats_emitter.get_latest_stats()
    update_metrics(stats=stats, event_counts=[])
    content, content_type = get_metrics()
    return Response(content=content, media_type=content_type)
