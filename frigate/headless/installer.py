from __future__ import annotations

import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess as sp
import time
import urllib.parse
from typing import Any, Callable


DiscoveryProbeFn = Callable[[str, float], bool]
StreamProbeFn = Callable[[str, str, float], dict[str, Any] | None]

DEFAULT_RTSP_PORTS = (554, 8554)
DEFAULT_ONVIF_PORTS = (80, 8000, 8080, 8899)
DEFAULT_DISCOVERY_PROFILES = ("hikvision", "dahua", "reolink", "uniview", "generic")


def _safe_import_psutil():
    try:
        import psutil  # type: ignore

        return psutil
    except Exception:
        return None


def _docker_memlimit_bytes() -> int:
    path = "/sys/fs/cgroup/memory.max"
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = handle.read().strip()
        if value.isdigit():
            return int(value)
    except Exception:
        pass
    return -1


def _detect_gpu_inventory() -> dict[str, Any]:
    inventory = {
        "accelerator": "software",
        "devices": [],
    }

    if os.path.exists("/dev/nvidia0") or shutil.which("nvidia-smi"):
        inventory["accelerator"] = "nvidia"
        query = shutil.which("nvidia-smi")
        if query:
            try:
                result = sp.run(
                    [query, "--query-gpu=name", "--format=csv,noheader"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                if result.returncode == 0:
                    inventory["devices"] = [
                        line.strip() for line in result.stdout.splitlines() if line.strip()
                    ]
            except Exception:
                pass
        if not inventory["devices"]:
            inventory["devices"] = ["nvidia-gpu"]
        return inventory

    if os.path.exists("/dev/dri"):
        inventory["accelerator"] = "vaapi"
        inventory["devices"] = ["vaapi-gpu"]
        return inventory

    return inventory


def build_hardware_profile(snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    snapshot = snapshot or {}
    psutil = _safe_import_psutil()

    logical_cpus = int(snapshot.get("logical_cpus") or os.cpu_count() or 1)
    physical_cpus = int(
        snapshot.get("physical_cpus")
        or (
            psutil.cpu_count(logical=False)
            if psutil is not None and hasattr(psutil, "cpu_count")
            else max(1, logical_cpus // 2)
        )
        or max(1, logical_cpus // 2)
    )

    total_mem_bytes = int(
        snapshot.get("total_mem_bytes")
        or (
            psutil.virtual_memory().total
            if psutil is not None and hasattr(psutil, "virtual_memory")
            else 0
        )
        or 0
    )
    docker_limit_bytes = int(snapshot.get("docker_limit_bytes") or _docker_memlimit_bytes())
    effective_mem_bytes = total_mem_bytes
    if docker_limit_bytes > 0:
        effective_mem_bytes = min(total_mem_bytes or docker_limit_bytes, docker_limit_bytes)

    disk_path = str(snapshot.get("disk_path") or "/")
    try:
        disk_free_bytes = int(snapshot.get("disk_free_bytes") or shutil.disk_usage(disk_path).free)
    except Exception:
        disk_free_bytes = int(snapshot.get("disk_free_bytes") or 0)

    gpu_inventory = snapshot.get("gpu_inventory")
    if not isinstance(gpu_inventory, dict):
        gpu_inventory = _detect_gpu_inventory()

    accelerator = str(gpu_inventory.get("accelerator", "software") or "software")
    decode_multiplier = {
        "nvidia": 2.2,
        "vaapi": 1.7,
        "software": 1.0,
    }.get(accelerator, 1.0)

    effective_mem_gib = max(0.5, effective_mem_bytes / (1024**3)) if effective_mem_bytes else 0.5
    cpu_budget = (physical_cpus * 1.35) + max(0, logical_cpus - physical_cpus) * 0.35
    memory_budget = effective_mem_gib / 1.4

    est_720p_5fps = max(1, int(min(cpu_budget * decode_multiplier, memory_budget * 1.6)))
    est_1080p_5fps = max(
        1, int(min(cpu_budget * 0.72 * decode_multiplier, memory_budget))
    )
    est_1080p_10fps = max(
        1, int(min(cpu_budget * 0.45 * decode_multiplier, memory_budget * 0.7))
    )

    recommended_tier = "edge_basic"
    if est_1080p_5fps >= 12:
        recommended_tier = "edge_robust"
    elif est_1080p_5fps >= 6:
        recommended_tier = "edge_medium"

    notes: list[str] = []
    if accelerator == "software":
        notes.append("Nenhuma aceleração de decode foi detectada; a estimativa é conservadora.")
    if effective_mem_gib < 8:
        notes.append("Memória efetiva abaixo de 8 GiB; priorize fewer streams ou resolução menor.")
    if disk_free_bytes and disk_free_bytes < 100 * (1024**3):
        notes.append("Espaço em disco livre baixo para retenção longa de gravações.")

    return {
        "generated_at": int(time.time()),
        "node": {
            "hostname": socket.gethostname(),
            "logical_cpus": logical_cpus,
            "physical_cpus": physical_cpus,
            "total_mem_bytes": total_mem_bytes,
            "effective_mem_bytes": effective_mem_bytes,
            "docker_limit_bytes": docker_limit_bytes,
            "disk_free_bytes": disk_free_bytes,
        },
        "gpu": gpu_inventory,
        "decode_acceleration": accelerator,
        "recommendation": {
            "tier": recommended_tier,
            "profiles": {
                "720p_5fps": est_720p_5fps,
                "1080p_5fps": est_1080p_5fps,
                "1080p_10fps": est_1080p_10fps,
            },
            "default_detect_fps": 5 if accelerator != "software" else 4,
            "confidence": "heuristic",
            "notes": notes,
        },
    }


def expand_scan_targets(targets: list[str], max_hosts: int = 256) -> list[str]:
    hosts: list[str] = []

    def add_host(value: str) -> None:
        if value not in hosts and len(hosts) < max_hosts:
            hosts.append(value)

    for raw in targets:
        value = str(raw or "").strip()
        if not value:
            continue

        if "/" in value:
            network = ipaddress.ip_network(value, strict=False)
            for host in network.hosts():
                add_host(str(host))
            continue

        range_match = re.match(
            r"^(?P<prefix>(?:\d{1,3}\.){3})(?P<start>\d{1,3})-(?P<end>\d{1,3})$",
            value,
        )
        if range_match:
            prefix = range_match.group("prefix")
            start = int(range_match.group("start"))
            end = int(range_match.group("end"))
            for last_octet in range(start, end + 1):
                add_host(f"{prefix}{last_octet}")
            continue

        add_host(value)

    return hosts[:max_hosts]


def probe_tcp_endpoint(address: str, timeout_sec: float) -> bool:
    host, _, port_raw = address.rpartition(":")
    if not host or not port_raw:
        return False

    try:
        with socket.create_connection((host, int(port_raw)), timeout=timeout_sec):
            return True
    except Exception:
        return False


def probe_rtsp_stream(url: str, ffprobe_path: str, timeout_sec: float) -> dict[str, Any] | None:
    ffprobe_bin = ffprobe_path if os.path.exists(ffprobe_path) else shutil.which("ffprobe")
    if not ffprobe_bin:
        return None

    command = [
        ffprobe_bin,
        "-rtsp_transport",
        "tcp",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        url,
    ]
    try:
        result = sp.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(1.0, timeout_sec),
            check=False,
        )
    except Exception:
        return None

    if result.returncode != 0 or not result.stdout:
        return None

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    streams = payload.get("streams", [])
    if not isinstance(streams, list):
        return None

    for stream in streams:
        if not isinstance(stream, dict) or stream.get("codec_type") != "video":
            continue
        width = int(stream.get("width", 0) or 0)
        height = int(stream.get("height", 0) or 0)
        if width <= 0 or height <= 0:
            continue
        return {
            "width": width,
            "height": height,
            "codec": stream.get("codec_name"),
        }

    return None


def _rtsp_url(host: str, port: int, path: str, username: str | None, password: str | None) -> str:
    auth = ""
    if username:
        auth = urllib.parse.quote(username, safe="")
        if password:
            auth += f":{urllib.parse.quote(password, safe='')}"
        auth += "@"
    return f"rtsp://{auth}{host}:{port}{path}"


def _profile_paths(profile: str, max_channels: int) -> list[tuple[int | None, str]]:
    if profile == "hikvision":
        return [
            (channel, f"/Streaming/Channels/{channel}01")
            for channel in range(1, max_channels + 1)
        ]
    if profile == "dahua":
        return [
            (channel, f"/cam/realmonitor?channel={channel}&subtype=0")
            for channel in range(1, max_channels + 1)
        ]
    if profile == "reolink":
        return [
            (channel, f"/h264Preview_{channel:02d}_main")
            for channel in range(1, max_channels + 1)
        ]
    if profile == "uniview":
        return [
            (channel, f"/media/video{channel}")
            for channel in range(1, max_channels + 1)
        ]
    return [
        (None, "/stream1"),
        (None, "/live"),
        (None, "/cam/realmonitor?channel=1&subtype=0"),
        (None, "/Streaming/Channels/101"),
    ]


def discover_camera_candidates(
    *,
    ffprobe_path: str,
    targets: list[str],
    username: str | None = None,
    password: str | None = None,
    rtsp_ports: list[int] | None = None,
    onvif_ports: list[int] | None = None,
    profiles: list[str] | None = None,
    max_hosts: int = 256,
    max_channels: int = 16,
    max_candidates: int = 128,
    timeout_sec: float = 2.0,
    port_probe: DiscoveryProbeFn = probe_tcp_endpoint,
    stream_probe: StreamProbeFn = probe_rtsp_stream,
) -> dict[str, Any]:
    hosts = expand_scan_targets(targets, max_hosts=max_hosts)
    rtsp_ports = rtsp_ports or list(DEFAULT_RTSP_PORTS)
    onvif_ports = onvif_ports or list(DEFAULT_ONVIF_PORTS)
    profiles = profiles or list(DEFAULT_DISCOVERY_PROFILES)

    candidates: list[dict[str, Any]] = []
    open_hosts: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for host in hosts:
        open_rtsp_ports = [
            port for port in rtsp_ports if port_probe(f"{host}:{port}", timeout_sec)
        ]
        open_onvif_ports = [
            port for port in onvif_ports if port_probe(f"{host}:{port}", timeout_sec)
        ]

        if not open_rtsp_ports and not open_onvif_ports:
            continue

        open_hosts.append(
            {
                "host": host,
                "rtsp_ports": open_rtsp_ports,
                "onvif_ports": open_onvif_ports,
            }
        )

        for port in open_rtsp_ports:
            for profile in profiles:
                for channel, path in _profile_paths(profile, max_channels):
                    url = _rtsp_url(host, port, path, username, password)
                    if url in seen_urls:
                        continue
                    stream = stream_probe(url, ffprobe_path, timeout_sec)
                    if stream is None:
                        continue
                    seen_urls.add(url)

                    candidate_id = f"{host}-{port}-{profile}-{channel or 'single'}"
                    source_type = "nvr_channel" if channel is not None else "camera"
                    suggested_name = (
                        f"nvr_{host.replace('.', '_')}_ch{int(channel):02d}"
                        if channel is not None
                        else f"cam_{host.replace('.', '_')}"
                    )
                    candidates.append(
                        {
                            "id": candidate_id,
                            "host": host,
                            "port": port,
                            "profile": profile,
                            "channel": channel,
                            "source_type": source_type,
                            "rtsp_url": url,
                            "resolution": {
                                "width": int(stream.get("width", 0) or 0),
                                "height": int(stream.get("height", 0) or 0),
                            },
                            "codec": stream.get("codec"),
                            "onvif_reachable": bool(open_onvif_ports),
                            "suggested_camera_name": suggested_name,
                        }
                    )
                    if len(candidates) >= max_candidates:
                        break
                if len(candidates) >= max_candidates:
                    break
            if len(candidates) >= max_candidates:
                break
        if len(candidates) >= max_candidates:
            break

    return {
        "generated_at": int(time.time()),
        "targets_scanned": hosts,
        "reachable_hosts": open_hosts,
        "candidates": candidates,
        "summary": {
            "hosts_scanned": len(hosts),
            "hosts_reachable": len(open_hosts),
            "candidates_found": len(candidates),
        },
        "connect_prompt": {
            "has_candidates": bool(candidates),
            "message": (
                "Deseja conectar agora as cameras descobertas?"
                if candidates
                else "Nenhuma camera/NVR foi validada com os parametros informados."
            ),
            "action": "POST /install/discovery/connect",
        },
    }


def _sanitize_camera_name(name: str, existing: set[str]) -> str:
    base = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_").lower() or "camera"
    if base[0].isdigit():
        base = f"cam_{base}"

    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}_{suffix}"
        suffix += 1
    existing.add(candidate)
    return candidate


def build_camera_connection_patch(
    *,
    selected_candidates: list[dict[str, Any]],
    existing_config: dict[str, Any],
    camera_name_prefix: str = "cam",
    detect_enabled: bool = True,
    record_enabled: bool = True,
) -> dict[str, Any]:
    cameras_patch: dict[str, Any] = {}
    go2rtc_streams: dict[str, str] = {}
    existing_names = set(existing_config.get("cameras", {}).keys())
    current_streams = (
        existing_config.get("go2rtc", {}).get("streams", {})
        if isinstance(existing_config.get("go2rtc", {}), dict)
        else {}
    )
    existing_stream_names = set(current_streams.keys()) if isinstance(current_streams, dict) else set()

    for item in selected_candidates:
        suggested_name = str(item.get("suggested_camera_name") or "camera")
        source_name = suggested_name
        if camera_name_prefix and not suggested_name.startswith(f"{camera_name_prefix}_"):
            source_name = f"{camera_name_prefix}_{suggested_name}"
        camera_name = _sanitize_camera_name(source_name, existing_names)
        stream_name = _sanitize_camera_name(camera_name, existing_stream_names)
        rtsp_url = str(item.get("rtsp_url") or "")
        if not rtsp_url:
            continue

        roles = ["detect"]
        if record_enabled:
            roles.insert(0, "record")

        camera_patch = {
            "enabled": True,
            "detect": {
                "enabled": detect_enabled,
            },
            "record": {
                "enabled": record_enabled,
            },
            "ffmpeg": {
                "inputs": [
                    {
                        "path": rtsp_url,
                        "roles": roles,
                    }
                ]
            },
            "live": {
                "streams": {
                    stream_name: stream_name,
                }
            },
        }

        cameras_patch[camera_name] = camera_patch
        go2rtc_streams[stream_name] = rtsp_url

    patch: dict[str, Any] = {}
    if cameras_patch:
        patch["cameras"] = cameras_patch
    if go2rtc_streams:
        patch["go2rtc"] = {"streams": go2rtc_streams}
    return patch
