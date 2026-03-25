from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


STATE_SCHEMA_VERSION = 1


def _now_ts() -> int:
    return int(time.time())


def _string_map(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in raw.items():
        key_str = str(key or '').strip()
        value_str = str(value or '').strip()
        if key_str and value_str:
            normalized[key_str] = value_str
    return normalized


def _roles_tuple(raw: Any, fallback: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return fallback
    values = tuple(str(item).strip() for item in raw if str(item).strip())
    return values or fallback


@dataclass(frozen=True)
class DesiredCameraState:
    camera_id: str
    stream_name: str = ''
    stream_url: str = ''
    ffmpeg_path: str = ''
    input_args: str = 'preset-rtsp-generic'
    roles: tuple[str, ...] = field(default_factory=lambda: ('record', 'detect'))
    hwaccel_args: str = ''
    enabled: bool = True
    detect_enabled: bool = True
    record_enabled: bool = True
    audio_enabled: bool = False
    origin: str = 'runtime_patch'
    profile: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'camera_id': self.camera_id,
            'stream_name': self.stream_name,
            'stream_url': self.stream_url,
            'ffmpeg_path': self.ffmpeg_path,
            'input_args': self.input_args,
            'roles': list(self.roles),
            'hwaccel_args': self.hwaccel_args,
            'enabled': self.enabled,
            'detect_enabled': self.detect_enabled,
            'record_enabled': self.record_enabled,
            'audio_enabled': self.audio_enabled,
            'origin': self.origin,
            'profile': self.profile,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, camera_id: str, payload: Any) -> 'DesiredCameraState':
        payload = payload if isinstance(payload, dict) else {}
        fallback_roles = ('record', 'detect')
        return cls(
            camera_id=camera_id,
            stream_name=str(payload.get('stream_name') or ''),
            stream_url=str(payload.get('stream_url') or ''),
            ffmpeg_path=str(payload.get('ffmpeg_path') or ''),
            input_args=str(payload.get('input_args') or 'preset-rtsp-generic'),
            roles=_roles_tuple(payload.get('roles'), fallback_roles),
            hwaccel_args=str(payload.get('hwaccel_args') or ''),
            enabled=bool(payload.get('enabled', True)),
            detect_enabled=bool(payload.get('detect_enabled', True)),
            record_enabled=bool(payload.get('record_enabled', True)),
            audio_enabled=bool(payload.get('audio_enabled', False)),
            origin=str(payload.get('origin') or 'runtime_patch'),
            profile=str(payload.get('profile') or ''),
            metadata=payload.get('metadata', {}) if isinstance(payload.get('metadata'), dict) else {},
        )


@dataclass(frozen=True)
class DesiredTenantState:
    tenant_id: str
    cameras: dict[str, DesiredCameraState] = field(default_factory=dict)
    go2rtc_streams: dict[str, str] = field(default_factory=dict)
    updated_at: int = field(default_factory=_now_ts)
    schema_version: int = STATE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            'tenant_id': self.tenant_id,
            'schema_version': self.schema_version,
            'updated_at': self.updated_at,
            'go2rtc_streams': dict(self.go2rtc_streams),
            'cameras': {
                camera_id: camera.to_dict() for camera_id, camera in self.cameras.items()
            },
        }

    @classmethod
    def from_dict(cls, tenant_id: str, payload: Any) -> 'DesiredTenantState':
        payload = payload if isinstance(payload, dict) else {}
        cameras_payload = payload.get('cameras', {}) if isinstance(payload.get('cameras'), dict) else {}
        cameras = {
            str(camera_id): DesiredCameraState.from_dict(str(camera_id), camera_payload)
            for camera_id, camera_payload in cameras_payload.items()
        }
        return cls(
            tenant_id=str(payload.get('tenant_id') or tenant_id),
            cameras=cameras,
            go2rtc_streams=_string_map(payload.get('go2rtc_streams')),
            updated_at=int(payload.get('updated_at') or _now_ts()),
            schema_version=int(payload.get('schema_version') or STATE_SCHEMA_VERSION),
        )


@dataclass(frozen=True)
class CameraOperationalState:
    camera_id: str
    status: str = 'unknown'
    process_fps: float = 0.0
    skipped_fps: float = 0.0
    last_error: str = ''
    source: str = 'runtime'
    last_transition_ts: int = field(default_factory=_now_ts)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'camera_id': self.camera_id,
            'status': self.status,
            'process_fps': self.process_fps,
            'skipped_fps': self.skipped_fps,
            'last_error': self.last_error,
            'source': self.source,
            'last_transition_ts': self.last_transition_ts,
            'details': self.details,
        }

    @classmethod
    def from_dict(cls, camera_id: str, payload: Any) -> 'CameraOperationalState':
        payload = payload if isinstance(payload, dict) else {}
        return cls(
            camera_id=camera_id,
            status=str(payload.get('status') or 'unknown'),
            process_fps=float(payload.get('process_fps', 0.0) or 0.0),
            skipped_fps=float(payload.get('skipped_fps', 0.0) or 0.0),
            last_error=str(payload.get('last_error') or ''),
            source=str(payload.get('source') or 'runtime'),
            last_transition_ts=int(payload.get('last_transition_ts') or _now_ts()),
            details=payload.get('details', {}) if isinstance(payload.get('details'), dict) else {},
        )


@dataclass(frozen=True)
class OperationalTenantState:
    tenant_id: str
    cameras: dict[str, CameraOperationalState] = field(default_factory=dict)
    updated_at: int = field(default_factory=_now_ts)
    schema_version: int = STATE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            'tenant_id': self.tenant_id,
            'schema_version': self.schema_version,
            'updated_at': self.updated_at,
            'cameras': {
                camera_id: camera.to_dict() for camera_id, camera in self.cameras.items()
            },
        }

    @classmethod
    def from_dict(cls, tenant_id: str, payload: Any) -> 'OperationalTenantState':
        payload = payload if isinstance(payload, dict) else {}
        cameras_payload = payload.get('cameras', {}) if isinstance(payload.get('cameras'), dict) else {}
        cameras = {
            str(camera_id): CameraOperationalState.from_dict(str(camera_id), camera_payload)
            for camera_id, camera_payload in cameras_payload.items()
        }
        return cls(
            tenant_id=str(payload.get('tenant_id') or tenant_id),
            cameras=cameras,
            updated_at=int(payload.get('updated_at') or _now_ts()),
            schema_version=int(payload.get('schema_version') or STATE_SCHEMA_VERSION),
        )


def apply_runtime_patch_to_desired_state(
    state: DesiredTenantState,
    runtime_patch: dict[str, Any],
    *,
    origin: str = 'runtime_patch',
) -> DesiredTenantState:
    if not isinstance(runtime_patch, dict) or not runtime_patch:
        return state

    next_streams = dict(state.go2rtc_streams)
    next_cameras = dict(state.cameras)

    go2rtc_patch = runtime_patch.get('go2rtc', {})
    if isinstance(go2rtc_patch, dict):
        next_streams.update(_string_map(go2rtc_patch.get('streams')))

    cameras_patch = runtime_patch.get('cameras', {})
    if isinstance(cameras_patch, dict):
        for camera_id_raw, camera_patch in cameras_patch.items():
            camera_id = str(camera_id_raw or '').strip()
            if not camera_id or not isinstance(camera_patch, dict):
                continue

            current = next_cameras.get(camera_id, DesiredCameraState(camera_id=camera_id))
            ffmpeg_patch = camera_patch.get('ffmpeg', {}) if isinstance(camera_patch.get('ffmpeg'), dict) else {}
            inputs = ffmpeg_patch.get('inputs', []) if isinstance(ffmpeg_patch.get('inputs'), list) else []
            first_input = inputs[0] if inputs and isinstance(inputs[0], dict) else {}

            live_patch = camera_patch.get('live', {}) if isinstance(camera_patch.get('live'), dict) else {}
            live_streams = live_patch.get('streams', {}) if isinstance(live_patch.get('streams'), dict) else {}
            stream_name = current.stream_name
            if live_streams:
                first_key = next(iter(live_streams.keys()))
                stream_name = str(live_streams.get(first_key) or first_key)
            elif not stream_name and camera_id in next_streams:
                stream_name = camera_id

            ffmpeg_path = str(first_input.get('path') or current.ffmpeg_path)
            stream_url = current.stream_url
            if stream_name and stream_name in next_streams:
                stream_url = str(next_streams[stream_name])
            elif ffmpeg_path:
                stream_url = ffmpeg_path

            roles = _roles_tuple(first_input.get('roles'), current.roles)
            if stream_name and stream_url:
                next_streams[stream_name] = stream_url

            audio_patch = camera_patch.get('audio', {}) if isinstance(camera_patch.get('audio'), dict) else {}
            detect_patch = camera_patch.get('detect', {}) if isinstance(camera_patch.get('detect'), dict) else {}
            record_patch = camera_patch.get('record', {}) if isinstance(camera_patch.get('record'), dict) else {}
            metadata: dict[str, Any] = {}
            if isinstance(camera_patch.get('onvif'), dict):
                metadata['onvif'] = camera_patch.get('onvif')

            next_cameras[camera_id] = DesiredCameraState(
                camera_id=camera_id,
                stream_name=stream_name,
                stream_url=stream_url,
                ffmpeg_path=ffmpeg_path,
                input_args=str(first_input.get('input_args') or current.input_args),
                roles=roles,
                hwaccel_args=str(ffmpeg_patch.get('hwaccel_args') or current.hwaccel_args),
                enabled=bool(camera_patch.get('enabled', current.enabled)),
                detect_enabled=bool(detect_patch.get('enabled', current.detect_enabled)),
                record_enabled=bool(record_patch.get('enabled', current.record_enabled)),
                audio_enabled=bool(audio_patch.get('enabled', current.audio_enabled or ('audio' in roles))),
                origin=origin,
                profile=str(camera_patch.get('profile') or current.profile),
                metadata=metadata or current.metadata,
            )

    return DesiredTenantState(
        tenant_id=state.tenant_id,
        cameras=next_cameras,
        go2rtc_streams=next_streams,
        updated_at=_now_ts(),
        schema_version=state.schema_version,
    )
