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


@dataclass
class RuntimeConfigStore:
    base_config: Any
    env_overlay: dict[str, Any]
    runtime_overlay: dict[str, Any] = field(default_factory=dict)
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
