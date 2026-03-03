"""Noise intelligence and auto-suggestion helpers."""

from __future__ import annotations

import time
from typing import Any


def _camera_overloaded(camera_stats: dict[str, Any]) -> bool:
    skipped_fps = float(camera_stats.get("skipped_fps", 0.0) or 0.0)
    adaptive_overload = int(camera_stats.get("adaptive_overload", 0) or 0)
    routing_drops = int(camera_stats.get("routing_quota_drops", 0) or 0)
    return skipped_fps >= 1.5 or adaptive_overload == 1 or routing_drops > 0


def _suggest_threshold(
    camera: str, label: str, current_threshold: float, tenant_id: str, now_ts: float
) -> dict[str, Any]:
    new_threshold = min(0.95, round(current_threshold + 0.05, 2))
    return {
        "id": f"{camera}-threshold-{label}-{int(now_ts)}",
        "tenant_id": tenant_id,
        "camera": camera,
        "type": "threshold",
        "risk": "low",
        "title": f"Aumentar threshold de {label}",
        "reason": "Taxa de fila/skip sugere ruido acima do ideal.",
        "estimated_impact": {
            "expected_noise_reduction_pct": 15,
            "expected_false_negative_risk_pct": 2,
        },
        "patch": {
            "cameras": {
                camera: {"objects": {"filters": {label: {"threshold": new_threshold}}}}
            }
        },
    }


def _suggest_cooldown(
    camera: str, current_cooldown: int, tenant_id: str, now_ts: float
) -> dict[str, Any]:
    new_cooldown = min(120, current_cooldown + 5)
    return {
        "id": f"{camera}-cooldown-{int(now_ts)}",
        "tenant_id": tenant_id,
        "camera": camera,
        "type": "cooldown",
        "risk": "low",
        "title": "Aumentar cooldown de notificacao",
        "reason": "Padrao de ruido indica repeticao de alertas em curto intervalo.",
        "estimated_impact": {
            "expected_noise_reduction_pct": 10,
            "expected_false_negative_risk_pct": 1,
        },
        "patch": {"cameras": {camera: {"notifications": {"cooldown": new_cooldown}}}},
    }


def _suggest_roi_profile(camera: str, tenant_id: str, now_ts: float) -> dict[str, Any]:
    return {
        "id": f"{camera}-roi-profile-{int(now_ts)}",
        "tenant_id": tenant_id,
        "camera": camera,
        "type": "roi",
        "risk": "medium",
        "title": "Ativar ROI scheduling baseline",
        "reason": "Camera apresenta sinais de ruido recorrente sem perfil de ROI ativo.",
        "estimated_impact": {
            "expected_noise_reduction_pct": 20,
            "expected_false_negative_risk_pct": 3,
        },
        "patch": {
            "cameras": {
                camera: {
                    "detect": {
                        "roi_scheduling": {
                            "enabled": True,
                            "profiles": [
                                {
                                    "name": "auto-noise-baseline",
                                    "version": 1,
                                    "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                                    "start_time": "00:00",
                                    "end_time": "23:59",
                                    "region_size_multiplier": 0.95,
                                }
                            ],
                        }
                    }
                }
            }
        },
    }


def _suggest_dynamic_mask(camera: str, tenant_id: str, now_ts: float) -> dict[str, Any]:
    return {
        "id": f"{camera}-mask-{int(now_ts)}",
        "tenant_id": tenant_id,
        "camera": camera,
        "type": "mask",
        "risk": "medium",
        "title": "Adicionar mascara dinamica em fonte de ruido",
        "reason": "Ruido recorrente identificado. Necessita validacao manual da geometria.",
        "estimated_impact": {
            "expected_noise_reduction_pct": 25,
            "expected_false_negative_risk_pct": 4,
        },
        "patch": None,
        "requires_manual_geometry": True,
    }


def generate_noise_suggestions(
    stats: dict[str, Any], effective_config: dict[str, Any], tenant_id: str
) -> list[dict[str, Any]]:
    now_ts = time.time()
    suggestions: list[dict[str, Any]] = []
    cameras_stats = stats.get("cameras", {}) if isinstance(stats, dict) else {}
    cameras_cfg = (
        effective_config.get("cameras", {}) if isinstance(effective_config, dict) else {}
    )

    for camera, camera_cfg in cameras_cfg.items():
        camera_stats = cameras_stats.get(camera, {})
        if not _camera_overloaded(camera_stats):
            continue

        filters = (
            camera_cfg.get("objects", {}).get("filters", {})
            if isinstance(camera_cfg, dict)
            else {}
        )
        for label, filter_cfg in filters.items():
            if not isinstance(filter_cfg, dict):
                continue
            current_threshold = float(filter_cfg.get("threshold", 0.7) or 0.7)
            if current_threshold < 0.9:
                suggestions.append(
                    _suggest_threshold(
                        camera, label, current_threshold, tenant_id, now_ts
                    )
                )
                break

        current_cooldown = int(
            camera_cfg.get("notifications", {}).get("cooldown", 0)
            if isinstance(camera_cfg, dict)
            else 0
        )
        if current_cooldown < 30:
            suggestions.append(_suggest_cooldown(camera, current_cooldown, tenant_id, now_ts))

        roi_enabled = bool(
            camera_cfg.get("detect", {}).get("roi_scheduling", {}).get("enabled", False)
            if isinstance(camera_cfg, dict)
            else False
        )
        if not roi_enabled:
            suggestions.append(_suggest_roi_profile(camera, tenant_id, now_ts))

        suggestions.append(_suggest_dynamic_mask(camera, tenant_id, now_ts))

    return suggestions
