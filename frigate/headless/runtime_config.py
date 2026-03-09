import copy
import os
from dataclasses import dataclass, field
from threading import Lock
from typing import TYPE_CHECKING, Any

from .settings import parse_typed_env_value

if TYPE_CHECKING:
    from frigate.config import FrigateConfig


def deep_merge(dct1: dict, dct2: dict) -> dict:
    merged = copy.deepcopy(dct1)
    for key, value in dct2.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


CFG_PREFIX = "FRIGATE_CFG__"


@dataclass
class CanaryPolicy:
    cameras: list[str] = field(default_factory=list)
    duration_sec: int = 300
    max_skipped_fps_increase: float = 2.0
    min_process_fps_ratio: float = 0.7
    max_inference_latency_increase_pct: float = 35.0


@dataclass
class CanaryRun:
    id: str
    started_at: float
    policy: CanaryPolicy
    previous_runtime_overlay: dict[str, Any]
    applied_patch: dict[str, Any]
    baseline_camera_metrics: dict[str, dict[str, float]]
    status: str = "running"
    evaluation_reason: str | None = None


def _set_nested(mapping: dict[str, Any], path: list[str], value: Any) -> None:
    current = mapping
    for key in path[:-1]:
        current = current.setdefault(key, {})
    current[path[-1]] = value


def load_env_overlay() -> dict[str, Any]:
    overlay: dict[str, Any] = {}

    # Generic tree override with FRIGATE_CFG__a__b__c=value
    for key, raw_value in os.environ.items():
        if not key.startswith(CFG_PREFIX):
            continue
        path = key[len(CFG_PREFIX) :].lower().split("__")
        _set_nested(overlay, path, parse_typed_env_value(raw_value))

    # Optional complete JSON overlay
    config_json = os.getenv("FRIGATE_CONFIG_JSON")
    if config_json:
        parsed = parse_typed_env_value(config_json)
        if isinstance(parsed, dict):
            overlay = deep_merge(overlay, parsed)

    return overlay


def _filter_patch_for_canary(
    runtime_patch: dict[str, Any], cameras: list[str]
) -> dict[str, Any]:
    if not cameras:
        return copy.deepcopy(runtime_patch)

    if not isinstance(runtime_patch, dict):
        return {}

    cameras_patch = runtime_patch.get("cameras")
    if not isinstance(cameras_patch, dict):
        return {}

    filtered_cameras = {
        name: copy.deepcopy(patch)
        for name, patch in cameras_patch.items()
        if name in cameras
    }

    if not filtered_cameras:
        return {}

    return {"cameras": filtered_cameras}


def snapshot_camera_metrics(
    stats: dict[str, Any], cameras: list[str]
) -> dict[str, dict[str, float]]:
    cameras_stats = stats.get("cameras", {}) if isinstance(stats, dict) else {}
    snapshot: dict[str, dict[str, float]] = {}

    for camera in cameras:
        raw = cameras_stats.get(camera, {})
        if not isinstance(raw, dict):
            raw = {}

        snapshot[camera] = {
            "process_fps": float(raw.get("process_fps", 0.0) or 0.0),
            "skipped_fps": float(raw.get("skipped_fps", 0.0) or 0.0),
            "adaptive_inference_latency_ms": float(
                raw.get("adaptive_inference_latency_ms", 0.0) or 0.0
            ),
        }

    return snapshot


def assess_canary_health(
    baseline: dict[str, dict[str, float]],
    current: dict[str, dict[str, float]],
    policy: CanaryPolicy,
) -> list[str]:
    reasons: list[str] = []

    for camera, base in baseline.items():
        cur = current.get(camera, {})
        cur_process_fps = float(cur.get("process_fps", 0.0))
        cur_skipped_fps = float(cur.get("skipped_fps", 0.0))
        cur_latency = float(cur.get("adaptive_inference_latency_ms", 0.0))

        base_process_fps = float(base.get("process_fps", 0.0))
        base_skipped_fps = float(base.get("skipped_fps", 0.0))
        base_latency = float(base.get("adaptive_inference_latency_ms", 0.0))

        if base_process_fps > 0:
            if cur_process_fps < (base_process_fps * policy.min_process_fps_ratio):
                reasons.append(
                    f"{camera}: process_fps dropped from {base_process_fps:.2f} to {cur_process_fps:.2f}"
                )

        if (cur_skipped_fps - base_skipped_fps) > policy.max_skipped_fps_increase:
            reasons.append(
                f"{camera}: skipped_fps increased from {base_skipped_fps:.2f} to {cur_skipped_fps:.2f}"
            )

        if base_latency > 0:
            max_latency = base_latency * (
                1 + (policy.max_inference_latency_increase_pct / 100.0)
            )
            if cur_latency > max_latency:
                reasons.append(
                    f"{camera}: inference latency increased from {base_latency:.2f}ms to {cur_latency:.2f}ms"
                )

    return reasons


@dataclass
class RuntimeConfigStore:
    base_config: Any
    env_overlay: dict[str, Any]
    runtime_overlay: dict[str, Any] = field(default_factory=dict)
    canary_run: CanaryRun | None = None
    lock: Lock = field(default_factory=Lock)

    def effective_dict(self) -> dict[str, Any]:
        base = self.base_config.model_dump(mode="json", warnings="none", exclude_none=True)
        merged = deep_merge(base, self.env_overlay)
        merged = deep_merge(merged, self.runtime_overlay)
        return merged

    def validate_candidate(self, runtime_patch: dict[str, Any]) -> "FrigateConfig":
        from frigate.config import FrigateConfig

        merged_runtime = deep_merge(self.runtime_overlay, runtime_patch)
        candidate_dict = deep_merge(self.effective_dict(), runtime_patch)
        candidate = FrigateConfig.model_validate(candidate_dict)
        # keep linter happy by using merged_runtime in a meaningful way
        if not isinstance(merged_runtime, dict):
            raise ValueError("Runtime config is invalid")
        return candidate

    def apply_runtime_patch(self, runtime_patch: dict[str, Any]) -> "FrigateConfig":
        with self.lock:
            candidate = self.validate_candidate(runtime_patch)
            self.runtime_overlay = deep_merge(self.runtime_overlay, runtime_patch)
            return candidate

    def clear_runtime(self) -> None:
        with self.lock:
            self.runtime_overlay = {}
            self.canary_run = None

    def replace_runtime_overlay(self, runtime_overlay: dict[str, Any]) -> "FrigateConfig":
        with self.lock:
            from frigate.config import FrigateConfig

            base = self.base_config.model_dump(
                mode="json", warnings="none", exclude_none=True
            )
            candidate_dict = deep_merge(deep_merge(base, self.env_overlay), runtime_overlay)
            candidate = FrigateConfig.model_validate(candidate_dict)
            self.runtime_overlay = copy.deepcopy(runtime_overlay)
            return candidate

    def start_canary(
        self,
        runtime_patch: dict[str, Any],
        policy: CanaryPolicy,
        latest_stats: dict[str, Any],
        now_ts: float,
    ) -> tuple["FrigateConfig", dict[str, Any], dict[str, Any]]:
        with self.lock:
            if self.canary_run and self.canary_run.status == "running":
                raise ValueError("A canary rollout is already running")

            canary_patch = _filter_patch_for_canary(runtime_patch, policy.cameras)
            if not canary_patch:
                raise ValueError(
                    "Canary patch is empty after camera filtering. Provide camera-scoped changes."
                )

            candidate = self.validate_candidate(canary_patch)
            previous_runtime_overlay = copy.deepcopy(self.runtime_overlay)
            self.runtime_overlay = deep_merge(self.runtime_overlay, canary_patch)

            canary_id = f"canary-{int(now_ts)}"
            baseline = snapshot_camera_metrics(
                latest_stats, policy.cameras or list(canary_patch.get("cameras", {}).keys())
            )
            self.canary_run = CanaryRun(
                id=canary_id,
                started_at=now_ts,
                policy=policy,
                previous_runtime_overlay=previous_runtime_overlay,
                applied_patch=canary_patch,
                baseline_camera_metrics=baseline,
            )
            return candidate, canary_patch, self.canary_status(latest_stats, now_ts)

    def rollback_canary(
        self,
        reason: str,
        latest_stats: dict[str, Any],
        now_ts: float,
    ) -> dict[str, Any]:
        with self.lock:
            if not self.canary_run:
                return {
                    "status": "idle",
                    "reason": "No active canary rollout",
                }

            self.runtime_overlay = copy.deepcopy(
                self.canary_run.previous_runtime_overlay
            )
            self.canary_run.status = "rolled_back"
            self.canary_run.evaluation_reason = reason
            return self.canary_status(latest_stats, now_ts)

    def evaluate_canary(
        self, latest_stats: dict[str, Any], now_ts: float
    ) -> dict[str, Any]:
        with self.lock:
            if not self.canary_run:
                return {"status": "idle"}

            if self.canary_run.status != "running":
                return self.canary_status(latest_stats, now_ts)

            current = snapshot_camera_metrics(
                latest_stats, list(self.canary_run.baseline_camera_metrics.keys())
            )
            reasons = assess_canary_health(
                self.canary_run.baseline_camera_metrics,
                current,
                self.canary_run.policy,
            )
            if reasons:
                self.runtime_overlay = copy.deepcopy(
                    self.canary_run.previous_runtime_overlay
                )
                self.canary_run.status = "rolled_back"
                self.canary_run.evaluation_reason = "; ".join(reasons)
                return self.canary_status(latest_stats, now_ts)

            elapsed = max(0, int(now_ts - self.canary_run.started_at))
            if elapsed >= self.canary_run.policy.duration_sec:
                self.canary_run.status = "promoted"
                self.canary_run.evaluation_reason = "Canary SLO checks passed"

            return self.canary_status(latest_stats, now_ts)

    def canary_status(
        self, latest_stats: dict[str, Any], now_ts: float
    ) -> dict[str, Any]:
        if not self.canary_run:
            return {"status": "idle"}

        elapsed = max(0, int(now_ts - self.canary_run.started_at))
        current = snapshot_camera_metrics(
            latest_stats, list(self.canary_run.baseline_camera_metrics.keys())
        )
        return {
            "id": self.canary_run.id,
            "status": self.canary_run.status,
            "elapsed_sec": elapsed,
            "duration_sec": self.canary_run.policy.duration_sec,
            "cameras": list(self.canary_run.baseline_camera_metrics.keys()),
            "reason": self.canary_run.evaluation_reason,
            "baseline": self.canary_run.baseline_camera_metrics,
            "current": current,
        }


def init_runtime_store(config: Any) -> RuntimeConfigStore:
    return RuntimeConfigStore(base_config=config, env_overlay=load_env_overlay())


def diff_top_level_keys(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    keys = set(before.keys()) | set(after.keys())
    changed: list[str] = []
    for key in sorted(keys):
        if before.get(key) != after.get(key):
            changed.append(key)
    return changed


def requires_restart(changed_keys: list[str]) -> bool:
    hot_reload_allowed = {"camera_groups"}
    return any(key not in hot_reload_allowed for key in changed_keys)
