import time
from typing import Any


def evaluate_readiness(
    *,
    stats: dict[str, Any],
    db_connected: bool,
    sse_health: dict[str, float | int],
    canary_status: dict[str, Any],
    started_at: float,
    warmup_sec: int,
    min_process_fps: float,
    max_skipped_process_ratio: float,
    max_sse_fill_ratio: float,
) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    reasons: list[str] = []
    warnings: list[str] = []
    now_ts = time.time()
    uptime_sec = max(0, int(now_ts - started_at))

    checks["db_connected"] = bool(db_connected)
    if not checks["db_connected"]:
        reasons.append("database_disconnected")

    checks["warmup_complete"] = uptime_sec >= max(0, int(warmup_sec))
    if not checks["warmup_complete"]:
        reasons.append("warmup_in_progress")

    cameras = stats.get("cameras", {}) if isinstance(stats, dict) else {}
    checks["camera_stats_available"] = bool(isinstance(cameras, dict) and cameras)
    if not checks["camera_stats_available"]:
        reasons.append("camera_stats_unavailable")

    missing_camera_processes: list[str] = []
    total_process_fps = 0.0
    total_skipped_fps = 0.0
    if isinstance(cameras, dict):
        for camera_name, camera_stats in cameras.items():
            if not isinstance(camera_stats, dict):
                continue
            total_process_fps += float(camera_stats.get("process_fps", 0.0) or 0.0)
            total_skipped_fps += float(camera_stats.get("skipped_fps", 0.0) or 0.0)
            detection_enabled = bool(camera_stats.get("detection_enabled", True))
            if not detection_enabled:
                continue
            if not camera_stats.get("pid") or not camera_stats.get("ffmpeg_pid"):
                missing_camera_processes.append(str(camera_name))

    checks["total_process_fps"] = round(total_process_fps, 2)
    checks["total_skipped_fps"] = round(total_skipped_fps, 2)
    checks["missing_camera_processes"] = missing_camera_processes

    if total_process_fps < max(0.0, float(min_process_fps)):
        reasons.append("process_fps_below_threshold")
    if missing_camera_processes:
        reasons.append("missing_camera_processes")

    skipped_ratio = total_skipped_fps / max(total_process_fps, 0.0001)
    checks["skipped_process_ratio"] = round(skipped_ratio, 4)
    if skipped_ratio > max(0.0, float(max_skipped_process_ratio)):
        warnings.append("high_skipped_process_ratio")

    max_fill_ratio = float(sse_health.get("max_fill_ratio", 0.0) or 0.0)
    checks["sse_subscribers"] = int(sse_health.get("subscribers", 0) or 0)
    checks["sse_max_fill_ratio"] = round(max_fill_ratio, 4)
    if max_fill_ratio >= max(0.0, float(max_sse_fill_ratio)):
        reasons.append("sse_backpressure_critical")
    elif max_fill_ratio >= (max_sse_fill_ratio * 0.8):
        warnings.append("sse_backpressure_warning")

    canary_state = str(canary_status.get("status", "idle"))
    checks["canary_status"] = canary_state
    if canary_state == "rolled_back":
        warnings.append("canary_rolled_back")

    ready = len(reasons) == 0
    mode = "normal"
    write_allowed = True
    if not ready:
        mode = "not_ready"
        write_allowed = False
    elif warnings:
        mode = "degraded_read_only"
        write_allowed = False

    return {
        "ready": ready,
        "mode": mode,
        "write_critical_allowed": write_allowed,
        "reasons": reasons,
        "warnings": warnings,
        "checks": checks,
        "uptime_sec": uptime_sec,
    }
