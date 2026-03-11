import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from frigate.const import CONFIG_DIR

DEFAULT_STATE_PATH = f"{CONFIG_DIR}/headless_state.json"
STATE_VERSION = 1


def _default_state() -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "updated_at": int(time.time()),
        "runtime_overlays": {},
        "triggers": {},
        "regions": {},
        "event_delivery_status": {
            "channels": {},
            "dead_letters": [],
            "last_updated": int(time.time()),
        },
        "storage_runtime": {
            "configs": {},
            "sync": {
                "backlog": 0,
                "throughput": 0,
                "failures": 0,
                "last_success_ts": 0,
                "dead_letters": [],
            },
        },
        "cms_runtime": {
            "edge_id": "",
            "config_version": 0,
            "etag": "",
            "last_sync_ts": 0,
            "last_error": "",
            "license": {
                "status": "unknown",
                "valid": False,
                "checked_at": 0,
                "expires_at": 0,
                "grace_until": 0,
                "reason": "not_configured",
            },
            "auth": {
                "mode": "",
                "status": "not_configured",
                "expires_at": 0,
            },
            "last_known_good": {
                "runtime_patch": {},
                "config_version": 0,
                "etag": "",
                "applied_at": 0,
            },
            "audit": [],
        },
    }


@dataclass
class HeadlessStateStore:
    path: str = DEFAULT_STATE_PATH
    _lock: Lock = field(default_factory=Lock)

    def _normalize(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return _default_state()

        state = _default_state()
        if isinstance(payload.get("runtime_overlays"), dict):
            state["runtime_overlays"] = payload["runtime_overlays"]
        if isinstance(payload.get("triggers"), dict):
            state["triggers"] = payload["triggers"]
        if isinstance(payload.get("regions"), dict):
            state["regions"] = payload["regions"]
        if isinstance(payload.get("event_delivery_status"), dict):
            state["event_delivery_status"] = payload["event_delivery_status"]
        if isinstance(payload.get("storage_runtime"), dict):
            state["storage_runtime"] = payload["storage_runtime"]
        if isinstance(payload.get("cms_runtime"), dict):
            state["cms_runtime"] = payload["cms_runtime"]
        if isinstance(payload.get("version"), int):
            state["version"] = payload["version"]
        return state

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not os.path.exists(self.path):
                return _default_state()
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception:
                return _default_state()
            return self._normalize(payload)

    def save(self, state: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            normalized = self._normalize(state)
            normalized["updated_at"] = int(time.time())
            base_dir = os.path.dirname(self.path) or "."
            os.makedirs(base_dir, exist_ok=True)

            fd, tmp_path = tempfile.mkstemp(prefix=".headless_state_", dir=base_dir)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                    json.dump(normalized, tmp_file, separators=(",", ":"), sort_keys=True)
                    tmp_file.flush()
                    os.fsync(tmp_file.fileno())
                os.replace(tmp_path, self.path)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            return normalized

    def choose_runtime_overlay(self, fixed_tenant_id: str | None = None) -> tuple[str, dict[str, Any]]:
        state = self.load()
        overlays = state.get("runtime_overlays", {})
        if not isinstance(overlays, dict) or not overlays:
            return ("default", {})

        if fixed_tenant_id:
            chosen = overlays.get(fixed_tenant_id, {})
            return (fixed_tenant_id, chosen if isinstance(chosen, dict) else {})

        default_overlay = overlays.get("default")
        if isinstance(default_overlay, dict):
            return ("default", default_overlay)

        tenant_id, overlay = next(iter(overlays.items()))
        if not isinstance(overlay, dict):
            return ("default", {})
        return (str(tenant_id), overlay)

    def put_runtime_overlay(self, tenant_id: str, runtime_overlay: dict[str, Any]) -> dict[str, Any]:
        state = self.load()
        overlays = state.setdefault("runtime_overlays", {})
        if not isinstance(overlays, dict):
            overlays = {}
            state["runtime_overlays"] = overlays
        overlays[tenant_id] = runtime_overlay
        return self.save(state)

    def put_triggers(self, triggers: dict[str, dict[str, Any]]) -> dict[str, Any]:
        state = self.load()
        state["triggers"] = triggers
        return self.save(state)

    def put_regions(self, regions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        state = self.load()
        state["regions"] = regions
        return self.save(state)

    def put_event_delivery_status(self, status: dict[str, Any]) -> dict[str, Any]:
        state = self.load()
        state["event_delivery_status"] = status
        return self.save(state)

    def put_storage_runtime(self, runtime: dict[str, Any]) -> dict[str, Any]:
        state = self.load()
        state["storage_runtime"] = runtime
        return self.save(state)

    def cms_runtime(self) -> dict[str, Any]:
        state = self.load()
        runtime = state.get("cms_runtime", {})
        if isinstance(runtime, dict):
            return runtime
        return _default_state()["cms_runtime"]

    def put_cms_runtime(self, runtime: dict[str, Any]) -> dict[str, Any]:
        state = self.load()
        state["cms_runtime"] = runtime
        return self.save(state)


def get_headless_state_store() -> HeadlessStateStore:
    return HeadlessStateStore(path=os.getenv("FRIGATE_HEADLESS_STATE_PATH", DEFAULT_STATE_PATH))
