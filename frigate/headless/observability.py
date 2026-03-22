import time
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _recent_camera_samples(
    stats_history: list[dict[str, Any]], camera_name: str, limit: int = 10
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for item in stats_history[-limit:]:
        camera_stats = item.get("cameras", {}).get(camera_name)
        if isinstance(camera_stats, dict):
            samples.append(camera_stats)
    return samples


def _average_metric(samples: list[dict[str, Any]], key: str) -> float:
    values = [_safe_float(sample.get(key, 0.0)) for sample in samples]
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _camera_config_lookup(frigate_config: Any, camera_name: str) -> Any:
    cameras = getattr(frigate_config, "cameras", {}) if frigate_config is not None else {}
    if isinstance(cameras, dict):
        return cameras.get(camera_name)
    return None


def _enabled_feature_flags(camera_config: Any) -> dict[str, bool]:
    if camera_config is None:
        return {
            "audio": False,
            "record": False,
            "review": False,
            "snapshots": False,
            "semantic_search": False,
            "face_recognition": False,
            "lpr": False,
        }

    return {
        "audio": bool(getattr(getattr(camera_config, "audio", None), "enabled", False)),
        "record": bool(getattr(getattr(camera_config, "record", None), "enabled", False)),
        "review": bool(getattr(getattr(camera_config, "review", None), "enabled", False)),
        "snapshots": bool(getattr(getattr(camera_config, "snapshots", None), "enabled", False)),
        "semantic_search": bool(
            getattr(getattr(camera_config, "semantic_search", None), "enabled", False)
        ),
        "face_recognition": bool(
            getattr(getattr(camera_config, "face_recognition", None), "enabled", False)
        ),
        "lpr": bool(getattr(getattr(camera_config, "lpr", None), "enabled", False)),
    }


def _shared_detect_record_input(camera_config: Any) -> bool:
    if camera_config is None:
        return False

    ffmpeg = getattr(camera_config, "ffmpeg", None)
    inputs = getattr(ffmpeg, "inputs", []) if ffmpeg is not None else []

    for stream_input in inputs or []:
        roles = getattr(stream_input, "roles", []) or []
        if "detect" in roles and "record" in roles:
            return True

    return False


def _process_lookup(stats: dict[str, Any], pid: Any) -> dict[str, Any]:
    cpu_usages = stats.get("cpu_usages", {}) if isinstance(stats, dict) else {}
    if not isinstance(cpu_usages, dict) or not pid:
        return {}
    item = cpu_usages.get(str(pid), {})
    return item if isinstance(item, dict) else {}


def _top_hot_processes(stats: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    cpu_usages = stats.get("cpu_usages", {}) if isinstance(stats, dict) else {}
    if not isinstance(cpu_usages, dict):
        return []

    items: list[dict[str, Any]] = []
    for pid, payload in cpu_usages.items():
        if not isinstance(payload, dict):
            continue
        items.append(
            {
                "pid": str(pid),
                "cpu": round(_safe_float(payload.get("cpu", 0.0)), 2),
                "mem": round(_safe_float(payload.get("mem", 0.0)), 2),
                "cmdline": str(payload.get("cmdline", "") or ""),
            }
        )

    items.sort(key=lambda item: item["cpu"], reverse=True)
    return items[:limit]


def _storage_entry(stats: dict[str, Any], path: str) -> dict[str, Any]:
    storage = stats.get("service", {}).get("storage", {}) if isinstance(stats, dict) else {}
    if not isinstance(storage, dict):
        return {}
    item = storage.get(path, {})
    return item if isinstance(item, dict) else {}


def _detect_load_units(width: int, height: int, fps: float) -> float:
    base_pixels = 1280 * 720
    pixels = max(1, width) * max(1, height)
    return round((pixels / base_pixels) * max(0.2, fps / 5.0), 2)


def build_observability_snapshot(
    *,
    readiness: dict[str, Any],
    delivery_status: dict[str, Any],
    rate_limit_audit: list[dict[str, Any]],
    storage_sync: dict[str, Any],
) -> dict[str, Any]:
    now = int(time.time())
    backlog = int(delivery_status.get("pending_total", 0))
    rate_limited = len(
        [item for item in rate_limit_audit[-200:] if item.get("event") == "rate_limit_rejected"]
    )
    errors = int(delivery_status.get("channels", {}).get("webhook", {}).get("failed", 0))
    throughput = int(storage_sync.get("throughput", 0))
    return {
        "ts": now,
        "readiness_mode": readiness.get("mode", "unknown"),
        "api_ready": bool(readiness.get("ready", False)),
        "event_backlog": backlog,
        "event_webhook_failures": errors,
        "rate_limit_rejections_recent": rate_limited,
        "storage_sync_throughput": throughput,
        "storage_sync_failures": int(storage_sync.get("failures", 0)),
        "slo": {
            "event_backlog_ok": backlog <= 500,
            "rate_limit_rejections_ok": rate_limited <= 200,
            "storage_sync_ok": int(storage_sync.get("failures", 0)) <= 100,
        },
    }


def evaluate_release_gate(snapshot: dict[str, Any]) -> dict[str, Any]:
    slo = snapshot.get("slo", {})
    failed = [name for name, ok in slo.items() if not ok]
    passed = len(failed) == 0 and bool(snapshot.get("api_ready", False))
    reasons: list[str] = []
    if not snapshot.get("api_ready", False):
        reasons.append("api_not_ready")
    reasons.extend([f"slo_failed:{name}" for name in failed])
    return {
        "passed": passed,
        "reasons": reasons,
        "snapshot": snapshot,
    }


def build_performance_diagnostics(
    *,
    stats: dict[str, Any],
    stats_history: list[dict[str, Any]],
    hardware_profile: dict[str, Any],
    frigate_config: Any,
) -> dict[str, Any]:
    now = int(time.time())
    cameras_stats = stats.get("cameras", {}) if isinstance(stats, dict) else {}
    cameras_stats = cameras_stats if isinstance(cameras_stats, dict) else {}
    detectors = stats.get("detectors", {}) if isinstance(stats, dict) else {}
    detectors = detectors if isinstance(detectors, dict) else {}
    recommendation = hardware_profile.get("recommendation", {})
    estimated_capacity = recommendation.get("profiles", {}) if isinstance(recommendation, dict) else {}

    diagnostics: dict[str, Any] = {
        "ts": now,
        "window_samples": min(len(stats_history), 10),
        "hardware_profile": {
            "decode_acceleration": hardware_profile.get("decode_acceleration", "unknown"),
            "tier": recommendation.get("tier", "unknown"),
            "estimated_capacity": estimated_capacity,
            "notes": recommendation.get("notes", []),
        },
        "host": {
            "camera_count": len(cameras_stats),
            "total_camera_fps": round(_safe_float(stats.get("camera_fps", 0.0)), 2),
            "total_process_fps": round(_safe_float(stats.get("process_fps", 0.0)), 2),
            "total_skipped_fps": round(_safe_float(stats.get("skipped_fps", 0.0)), 2),
            "total_detection_fps": round(_safe_float(stats.get("detection_fps", 0.0)), 2),
            "hot_processes": _top_hot_processes(stats),
            "detectors": {
                name: {
                    "inference_speed_ms": round(
                        _safe_float(detector_stats.get("inference_speed", 0.0)), 2
                    ),
                    "pid": detector_stats.get("pid"),
                }
                for name, detector_stats in detectors.items()
                if isinstance(detector_stats, dict)
            },
            "storage": {
                "recordings": _storage_entry(stats, "/media/frigate/recordings"),
                "clips": _storage_entry(stats, "/media/frigate/clips"),
                "cache": _storage_entry(stats, "/tmp/cache"),
            },
        },
        "cameras": {},
        "issues": [],
        "recommendations": [],
    }

    total_requested_load = 0.0
    overloaded_cameras = 0
    recommendation_set: set[str] = set()
    host_issue_kinds: set[str] = set()

    for camera_name, camera_stats in cameras_stats.items():
        if not isinstance(camera_stats, dict):
            continue

        camera_config = _camera_config_lookup(frigate_config, camera_name)
        samples = _recent_camera_samples(stats_history, camera_name)
        if not samples:
            samples = [camera_stats]

        detect_config = getattr(camera_config, "detect", None)
        width = _safe_int(getattr(detect_config, "width", None), 1280)
        height = _safe_int(getattr(detect_config, "height", None), 720)
        requested_detect_fps = _safe_float(
            getattr(detect_config, "fps", None),
            _safe_float(camera_stats.get("detection_fps", 0.0)),
        )
        requested_detect_fps = max(0.0, requested_detect_fps)
        detect_load_units = _detect_load_units(width, height, requested_detect_fps or 5.0)
        total_requested_load += detect_load_units

        avg_camera_fps = _average_metric(samples, "camera_fps")
        avg_process_fps = _average_metric(samples, "process_fps")
        avg_skipped_fps = _average_metric(samples, "skipped_fps")
        avg_detection_fps = _average_metric(samples, "detection_fps")
        avg_inference_latency_ms = _average_metric(samples, "adaptive_inference_latency_ms")

        process_ratio = round(avg_process_fps / max(requested_detect_fps, 0.0001), 2)
        skipped_ratio = round(avg_skipped_fps / max(avg_process_fps, 0.0001), 2)
        source_ratio = round(avg_camera_fps / max(requested_detect_fps, 0.0001), 2)
        feature_flags = _enabled_feature_flags(camera_config)
        feature_load_score = len([flag for flag in feature_flags.values() if flag])
        shared_detect_record = _shared_detect_record_input(camera_config)

        ffmpeg_stats = _process_lookup(stats, camera_stats.get("ffmpeg_pid"))
        detect_stats = _process_lookup(stats, camera_stats.get("pid"))
        ffmpeg_cpu = round(_safe_float(ffmpeg_stats.get("cpu", 0.0)), 2)
        detect_cpu = round(_safe_float(detect_stats.get("cpu", 0.0)), 2)

        bottlenecks: list[dict[str, Any]] = []
        camera_recommendations: list[str] = []

        if requested_detect_fps > 0 and process_ratio < 0.8 and avg_skipped_fps >= 1.0:
            overloaded_cameras += 1

        if (
            ffmpeg_cpu >= 70.0
            and (
                str(hardware_profile.get("decode_acceleration", "software")) == "software"
                or avg_camera_fps > avg_process_fps * 1.3
            )
        ):
            bottlenecks.append(
                {
                    "kind": "decode_pressure",
                    "severity": "high" if ffmpeg_cpu >= 85.0 else "medium",
                    "reason": "FFmpeg CPU alto com sinais de decode pressionado.",
                }
            )
            camera_recommendations.append(
                "Ative hwaccel real ou use substream dedicado para detect com menor resolucao."
            )

        if process_ratio < 0.8 and (
            avg_inference_latency_ms >= 120.0 or detect_cpu >= 70.0 or avg_skipped_fps >= 1.0
        ):
            bottlenecks.append(
                {
                    "kind": "inference_pressure",
                    "severity": "high" if avg_inference_latency_ms >= 180.0 else "medium",
                    "reason": "A deteccao esta abaixo da meta com latencia ou CPU de inferencia elevados.",
                }
            )
            camera_recommendations.append(
                "Reduza detect.fps ou resolucao de detect, ou distribua a carga para acelerador ou outro no."
            )

        if shared_detect_record and (width * height >= 1920 * 1080 or requested_detect_fps > 5.0):
            bottlenecks.append(
                {
                    "kind": "stream_configuration",
                    "severity": "medium",
                    "reason": "Detect e record compartilham o mesmo stream em carga relativamente alta.",
                }
            )
            camera_recommendations.append(
                "Separe stream de detect e stream de record para reduzir decode e banda desnecessarios."
            )

        if requested_detect_fps > 0 and source_ratio < 0.8 and avg_skipped_fps < 0.5:
            bottlenecks.append(
                {
                    "kind": "source_stream_under_delivery",
                    "severity": "medium",
                    "reason": "A camera esta entregando menos FPS do que o alvo configurado.",
                }
            )
            camera_recommendations.append(
                "Revise RTSP ou NVR, bitrate, transporte e qualidade do substream de detect."
            )

        if feature_load_score >= 3 and (avg_skipped_fps >= 1.0 or process_ratio < 0.8):
            bottlenecks.append(
                {
                    "kind": "feature_pressure",
                    "severity": "medium",
                    "reason": "A camera combina varios recursos que aumentam o custo do pipeline.",
                }
            )
            camera_recommendations.append(
                "Desative audio, snapshots ou review nas cameras nao criticas para aliviar o pipeline."
            )

        diagnostics["cameras"][camera_name] = {
            "requested_detect_fps": requested_detect_fps,
            "detect_resolution": {"width": width, "height": height},
            "detect_load_units_720p_5fps": detect_load_units,
            "averages": {
                "camera_fps": avg_camera_fps,
                "process_fps": avg_process_fps,
                "skipped_fps": avg_skipped_fps,
                "detection_fps": avg_detection_fps,
                "inference_latency_ms": avg_inference_latency_ms,
            },
            "process_ratio": process_ratio,
            "skipped_ratio": skipped_ratio,
            "source_ratio": source_ratio,
            "ffmpeg_cpu_percent": ffmpeg_cpu,
            "detect_cpu_percent": detect_cpu,
            "feature_flags": feature_flags,
            "feature_load_score": feature_load_score,
            "shared_detect_record_stream": shared_detect_record,
            "bottlenecks": bottlenecks,
            "recommendations": camera_recommendations,
        }

        for item in camera_recommendations:
            recommendation_set.add(item)

    capacity_720p = max(
        1.0, _safe_float(estimated_capacity.get("720p_5fps", 0.0), default=1.0)
    )
    capacity_ratio = round(total_requested_load / capacity_720p, 2)
    diagnostics["host"]["requested_detect_load_720p_5fps"] = round(total_requested_load, 2)
    diagnostics["host"]["estimated_capacity_720p_5fps"] = round(capacity_720p, 2)
    diagnostics["host"]["capacity_utilization"] = capacity_ratio
    diagnostics["host"]["overloaded_cameras"] = overloaded_cameras

    if capacity_ratio > 1.0:
        host_issue_kinds.add("camera_capacity_exceeded")
        recommendation_set.add(
            "A carga total de detect excede a capacidade estimada; reduza FPS ou distribua cameras entre nos."
        )

    record_storage = diagnostics["host"]["storage"].get("recordings", {})
    cache_storage = diagnostics["host"]["storage"].get("cache", {})
    record_free = _safe_float(record_storage.get("free", 0.0))
    record_total = _safe_float(record_storage.get("total", 0.0))
    cache_free = _safe_float(cache_storage.get("free", 0.0))
    cache_total = _safe_float(cache_storage.get("total", 0.0))
    if (record_total > 0 and record_free / record_total < 0.12) or (
        cache_total > 0 and cache_free / cache_total < 0.12
    ):
        host_issue_kinds.add("storage_pressure")
        recommendation_set.add(
            "O armazenamento esta sob pressao; ajuste retencao, snapshots ou mova gravacoes para storage mais rapido."
        )

    hot_processes = diagnostics["host"]["hot_processes"]
    if hot_processes and _safe_float(hot_processes[0].get("cpu", 0.0)) >= 85.0:
        host_issue_kinds.add("cpu_pressure")

    if str(hardware_profile.get("decode_acceleration", "software")) == "software" and total_requested_load > 2.0:
        host_issue_kinds.add("decode_without_hwaccel")
        recommendation_set.add(
            "Nenhuma aceleracao de decode foi detectada; ative hwaccel ou use substreams mais leves."
        )

    for kind in sorted(host_issue_kinds):
        diagnostics["issues"].append({"kind": kind})

    diagnostics["recommendations"] = sorted(recommendation_set)
    return diagnostics
