import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _parse_hhmm(value: str) -> tuple[int, int]:
    hh, mm = value.split(":")
    return int(hh), int(mm)


def _within_window(now_hhmm: str, start: str, end: str) -> bool:
    now_h, now_m = _parse_hhmm(now_hhmm)
    st_h, st_m = _parse_hhmm(start)
    en_h, en_m = _parse_hhmm(end)
    now = now_h * 60 + now_m
    start_m = st_h * 60 + st_m
    end_m = en_h * 60 + en_m
    if start_m <= end_m:
        return start_m <= now <= end_m
    return now >= start_m or now <= end_m


@dataclass
class AdaptiveTuningManager:
    state: dict[str, Any] = field(
        default_factory=lambda: {
            "segments": {},
            "segment_baseline": {},
            "segment_limits": {},
            "health_scores": {},
            "day_night_profiles": {},
            "adaptive_rules": {},
            "audit": [],
        }
    )

    def classify_camera(self, camera_id: str, segment: str) -> dict[str, Any]:
        self.state["segments"][camera_id] = {
            "segment": segment,
            "updated_at": int(time.time()),
        }
        return self.state["segments"][camera_id]

    def set_segment_limits(self, segment: str, limits: dict[str, float]) -> dict[str, Any]:
        self.state["segment_limits"][segment] = {k: float(v) for k, v in limits.items()}
        self.state["segment_limits"][segment]["updated_at"] = int(time.time())
        return self.state["segment_limits"][segment]

    def capture_baseline(self, stats: dict[str, Any]) -> dict[str, Any]:
        cameras = stats.get("cameras", {}) if isinstance(stats, dict) else {}
        grouped: dict[str, dict[str, list[float]]] = {}
        for camera_id, camera_stats in cameras.items():
            segment = self.state["segments"].get(camera_id, {}).get("segment", "unclassified")
            grouped.setdefault(
                segment,
                {"process_fps": [], "skipped_fps": [], "queue_depth": [], "drop_rate": []},
            )
            if isinstance(camera_stats, dict):
                grouped[segment]["process_fps"].append(float(camera_stats.get("process_fps", 0.0) or 0.0))
                grouped[segment]["skipped_fps"].append(float(camera_stats.get("skipped_fps", 0.0) or 0.0))
                grouped[segment]["queue_depth"].append(float(camera_stats.get("queue_depth", 0.0) or 0.0))
                grouped[segment]["drop_rate"].append(float(camera_stats.get("drop_rate", 0.0) or 0.0))

        baseline: dict[str, Any] = {}
        for segment, values in grouped.items():
            baseline[segment] = {
                "avg_process_fps": round(sum(values["process_fps"]) / max(1, len(values["process_fps"])), 2),
                "avg_skipped_fps": round(sum(values["skipped_fps"]) / max(1, len(values["skipped_fps"])), 2),
                "avg_queue_depth": round(sum(values["queue_depth"]) / max(1, len(values["queue_depth"])), 2),
                "avg_drop_rate": round(sum(values["drop_rate"]) / max(1, len(values["drop_rate"])), 3),
                "updated_at": int(time.time()),
            }
        self.state["segment_baseline"] = baseline
        self._recompute_health_scores()
        return baseline

    def _recompute_health_scores(self) -> None:
        scores: dict[str, float] = {}
        for camera_id, seg_data in self.state["segments"].items():
            segment = seg_data.get("segment")
            baseline = self.state["segment_baseline"].get(segment, {})
            score = 100.0
            score -= min(40.0, float(baseline.get("avg_skipped_fps", 0.0)) * 10.0)
            score -= min(40.0, float(baseline.get("avg_drop_rate", 0.0)) * 100.0)
            score -= min(20.0, float(baseline.get("avg_queue_depth", 0.0)) / 10.0)
            scores[camera_id] = round(max(0.0, score), 2)
        self.state["health_scores"] = scores

    def upsert_day_night_profile(
        self,
        camera_id: str,
        *,
        day_profile: dict[str, Any],
        night_profile: dict[str, Any],
        day_start: str = "06:00",
        night_start: str = "18:00",
    ) -> dict[str, Any]:
        item = {
            "day_profile": day_profile,
            "night_profile": night_profile,
            "day_start": day_start,
            "night_start": night_start,
            "updated_at": int(time.time()),
            "active_profile": "day",
        }
        self.state["day_night_profiles"][camera_id] = item
        return item

    def evaluate_day_night(self, camera_id: str, now_hhmm: str | None = None) -> dict[str, Any]:
        profile = self.state["day_night_profiles"].get(camera_id)
        if not profile:
            raise ValueError("profile_not_found")
        now_hhmm = now_hhmm or datetime.utcnow().strftime("%H:%M")
        is_day = _within_window(now_hhmm, profile["day_start"], profile["night_start"])
        active = "day" if is_day else "night"
        profile["active_profile"] = active
        audit = {
            "camera_id": camera_id,
            "event": "profile_switch",
            "active_profile": active,
            "at": int(time.time()),
        }
        self.state["audit"].append(audit)
        self.state["audit"] = self.state["audit"][-500:]
        return {"camera_id": camera_id, "active_profile": active, "profile": profile[f"{active}_profile"]}

    def upsert_adaptive_rule(
        self,
        camera_id: str,
        label: str,
        *,
        min_threshold: float,
        max_threshold: float,
        min_cooldown: int,
        max_cooldown: int,
        current_threshold: float,
        current_cooldown: int,
    ) -> dict[str, Any]:
        key = f"{camera_id}:{label}"
        item = {
            "camera_id": camera_id,
            "label": label,
            "min_threshold": float(min_threshold),
            "max_threshold": float(max_threshold),
            "min_cooldown": int(min_cooldown),
            "max_cooldown": int(max_cooldown),
            "current_threshold": float(current_threshold),
            "current_cooldown": int(current_cooldown),
            "updated_at": int(time.time()),
        }
        self.state["adaptive_rules"][key] = item
        return item

    def evaluate_rule(
        self, camera_id: str, label: str, *, repeat_rate: float, is_critical: bool = False
    ) -> dict[str, Any]:
        key = f"{camera_id}:{label}"
        item = self.state["adaptive_rules"].get(key)
        if not item:
            raise ValueError("rule_not_found")
        threshold = float(item["current_threshold"])
        cooldown = int(item["current_cooldown"])
        if repeat_rate > 1.0:
            step = 0.03 if is_critical else 0.05
            threshold = min(float(item["max_threshold"]), threshold + step)
            cooldown = min(int(item["max_cooldown"]), cooldown + (2 if is_critical else 5))
        elif repeat_rate < 0.3:
            step = 0.01 if is_critical else 0.03
            threshold = max(float(item["min_threshold"]), threshold - step)
            cooldown = max(int(item["min_cooldown"]), cooldown - (1 if is_critical else 3))
        item["current_threshold"] = round(threshold, 3)
        item["current_cooldown"] = int(cooldown)
        audit = {
            "camera_id": camera_id,
            "label": label,
            "event": "adaptive_rule_adjusted",
            "repeat_rate": repeat_rate,
            "is_critical": is_critical,
            "new_threshold": item["current_threshold"],
            "new_cooldown": item["current_cooldown"],
            "at": int(time.time()),
        }
        self.state["audit"].append(audit)
        self.state["audit"] = self.state["audit"][-500:]
        return item

    def snapshot(self) -> dict[str, Any]:
        return self.state
