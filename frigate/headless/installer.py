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
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from typing import Any, Callable


DiscoveryProbeFn = Callable[[str, float], bool]
StreamProbeFn = Callable[[str, str, float], dict[str, Any] | None]
OnvifDiscoverFn = Callable[..., list[dict[str, Any]]]
OnvifDeviceFn = Callable[[str, str | None, str | None, float], dict[str, Any]]
OnvifProfilesFn = Callable[[str, str | None, str | None, float], list[dict[str, Any]]]

DEFAULT_RTSP_PORTS = (554, 8554)
DEFAULT_ONVIF_PORTS = (80, 8000, 8080, 8899)
DEFAULT_DISCOVERY_PROFILES = ("hikvision", "dahua", "reolink", "uniview", "generic")
WS_DISCOVERY_ADDR = ("239.255.255.250", 3702)
SOAP_ENV_NS = "http://www.w3.org/2003/05/soap-envelope"
WS_DISCOVERY_NS = "http://schemas.xmlsoap.org/ws/2005/04/discovery"
WS_ADDRESSING_NS = "http://schemas.xmlsoap.org/ws/2004/08/addressing"
ONVIF_DEVICE_NS = "http://www.onvif.org/ver10/device/wsdl"
ONVIF_MEDIA_NS = "http://www.onvif.org/ver10/media/wsdl"
ONVIF_MEDIA2_NS = "http://www.onvif.org/ver20/media/wsdl"
ONVIF_SCHEMA_NS = "http://www.onvif.org/ver10/schema"

NS = {
    "s": SOAP_ENV_NS,
    "a": WS_ADDRESSING_NS,
    "d": WS_DISCOVERY_NS,
    "tds": ONVIF_DEVICE_NS,
    "trt": ONVIF_MEDIA_NS,
    "tr2": ONVIF_MEDIA2_NS,
    "tt": ONVIF_SCHEMA_NS,
}


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
        audio_streams = [
            item
            for item in streams
            if isinstance(item, dict) and item.get("codec_type") == "audio"
        ]
        fps_raw = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/1"
        fps = 0.0
        try:
            numerator, denominator = str(fps_raw).split("/", 1)
            fps = float(numerator) / max(float(denominator), 1.0)
        except Exception:
            fps = 0.0
        return {
            "width": width,
            "height": height,
            "codec": stream.get("codec_name"),
            "fps": round(fps, 2),
            "has_audio": bool(audio_streams),
            "audio_codec": audio_streams[0].get("codec_name") if audio_streams else None,
        }

    return None


def _soap_envelope(action: str, body: str, message_id: str | None = None) -> bytes:
    message_id = message_id or f"uuid:{uuid.uuid4()}"
    payload = f"""
    <s:Envelope xmlns:s="{SOAP_ENV_NS}" xmlns:a="{WS_ADDRESSING_NS}" xmlns:d="{WS_DISCOVERY_NS}">
      <s:Header>
        <a:Action s:mustUnderstand="1">{action}</a:Action>
        <a:MessageID>{message_id}</a:MessageID>
        <a:To s:mustUnderstand="1">urn:schemas-xmlsoap-org:ws:2005:04:discovery</a:To>
      </s:Header>
      <s:Body>{body}</s:Body>
    </s:Envelope>
    """
    return payload.encode("utf-8")


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _text(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None else ""


def ws_discover_onvif_devices(
    *,
    targets: list[str] | None = None,
    timeout_sec: float = 2.0,
    repeat_count: int = 2,
) -> list[dict[str, Any]]:
    target_hosts = set(expand_scan_targets(targets or [], max_hosts=4096))
    message = _soap_envelope(
        f"{WS_DISCOVERY_NS}/Probe",
        (
            f'<d:Probe xmlns:d="{WS_DISCOVERY_NS}">'
            f'<dn:Types xmlns:dn="{ONVIF_SCHEMA_NS}" xmlns:tds="{ONVIF_DEVICE_NS}">'
            "dn:NetworkVideoTransmitter tds:Device"
            "</dn:Types>"
            f"</d:Probe>"
        ),
    )

    responses: dict[str, dict[str, Any]] = {}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    except Exception:
        return []
    try:
        sock.settimeout(timeout_sec)
        ttl = 2
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        for _ in range(max(1, repeat_count)):
            try:
                sock.sendto(message, WS_DISCOVERY_ADDR)
            except Exception:
                continue

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                break
            except Exception:
                break

            device = parse_ws_discovery_match(data, addr[0])
            if not device:
                continue
            host = str(device.get("host") or "")
            if target_hosts and host and host not in target_hosts:
                continue
            response_key = str(device.get("urn") or device.get("xaddr") or host)
            responses[response_key] = device
    finally:
        sock.close()

    return list(responses.values())


def parse_ws_discovery_match(payload: bytes, fallback_host: str | None = None) -> dict[str, Any] | None:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return None

    probe_match = root.find(".//d:ProbeMatch", NS)
    if probe_match is None:
        return None

    xaddrs_raw = _text(probe_match.find("d:XAddrs", NS))
    xaddrs = [item.strip() for item in xaddrs_raw.split() if item.strip()]
    xaddr = xaddrs[0] if xaddrs else ""
    scopes_raw = _text(probe_match.find("d:Scopes", NS))
    scopes = [item.strip() for item in scopes_raw.split() if item.strip()]
    urn = _text(probe_match.find("a:EndpointReference/a:Address", NS))
    types = _text(probe_match.find("d:Types", NS))

    host = fallback_host or ""
    port = 0
    if xaddr:
        parsed = urllib.parse.urlparse(xaddr)
        if parsed.hostname:
            host = parsed.hostname
        if parsed.port:
            port = parsed.port

    return {
        "host": host,
        "port": port,
        "xaddr": xaddr,
        "xaddrs": xaddrs,
        "scopes": scopes,
        "urn": urn,
        "types": types,
        "discovery": "ws-discovery",
    }


def _build_http_opener(
    service_url: str, username: str | None, password: str | None
) -> urllib.request.OpenerDirector:
    handlers: list[Any] = []
    if username:
        password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(None, service_url, username, password or "")
        handlers.append(urllib.request.HTTPDigestAuthHandler(password_mgr))
        handlers.append(urllib.request.HTTPBasicAuthHandler(password_mgr))
    return urllib.request.build_opener(*handlers)


def onvif_soap_call(
    service_url: str,
    action: str,
    body: str,
    username: str | None,
    password: str | None,
    timeout_sec: float,
) -> ET.Element:
    opener = _build_http_opener(service_url, username, password)
    request = urllib.request.Request(
        service_url,
        data=(
            f'<s:Envelope xmlns:s="{SOAP_ENV_NS}" xmlns:tds="{ONVIF_DEVICE_NS}" '
            f'xmlns:trt="{ONVIF_MEDIA_NS}" xmlns:tr2="{ONVIF_MEDIA2_NS}" xmlns:tt="{ONVIF_SCHEMA_NS}">'
            f"<s:Body>{body}</s:Body></s:Envelope>"
        ).encode("utf-8"),
        headers={
            "Content-Type": 'application/soap+xml; charset=utf-8; action="%s"' % action,
            "User-Agent": "frigate-headless-installer",
        },
        method="POST",
    )
    with opener.open(request, timeout=max(1.0, timeout_sec)) as response:
        data = response.read()
    return ET.fromstring(data)


def fetch_onvif_device_metadata(
    service_url: str,
    username: str | None,
    password: str | None,
    timeout_sec: float,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "service_url": service_url,
        "manufacturer": "",
        "model": "",
        "firmware_version": "",
        "serial_number": "",
        "hardware_id": "",
        "capabilities": {},
    }

    try:
        info_root = onvif_soap_call(
            service_url,
            f"{ONVIF_DEVICE_NS}/GetDeviceInformation",
            "<tds:GetDeviceInformation/>",
            username,
            password,
            timeout_sec,
        )
        response = info_root.find(".//tds:GetDeviceInformationResponse", NS)
        if response is not None:
            for key, field in (
                ("manufacturer", "Manufacturer"),
                ("model", "Model"),
                ("firmware_version", "FirmwareVersion"),
                ("serial_number", "SerialNumber"),
                ("hardware_id", "HardwareId"),
            ):
                metadata[key] = _text(next((child for child in response if _local_name(child.tag) == field), None))
    except Exception:
        pass

    try:
        capabilities_root = onvif_soap_call(
            service_url,
            f"{ONVIF_DEVICE_NS}/GetCapabilities",
            "<tds:GetCapabilities><tds:Category>All</tds:Category></tds:GetCapabilities>",
            username,
            password,
            timeout_sec,
        )
        response = capabilities_root.find(".//tds:GetCapabilitiesResponse", NS)
        if response is not None:
            capabilities = response.find(".//tds:Capabilities", NS)
            if capabilities is not None:
                media = capabilities.find(".//tt:Media", NS)
                if media is not None:
                    metadata["capabilities"]["media_xaddr"] = _text(
                        next(
                            (child for child in media if _local_name(child.tag) == "XAddr"),
                            None,
                        )
                    )
                media2 = capabilities.find(".//tt:Media2", NS)
                if media2 is not None:
                    metadata["capabilities"]["media2_xaddr"] = _text(
                        next(
                            (child for child in media2 if _local_name(child.tag) == "XAddr"),
                            None,
                        )
                    )
                events = capabilities.find(".//tt:Events", NS)
                metadata["capabilities"]["events"] = events is not None
    except Exception:
        pass

    return metadata


def _media_service_candidates(service_url: str, metadata: dict[str, Any]) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    media_xaddr = str(metadata.get("capabilities", {}).get("media_xaddr") or "")
    media2_xaddr = str(metadata.get("capabilities", {}).get("media2_xaddr") or "")
    if media_xaddr:
        candidates.append(("media", media_xaddr))
    if media2_xaddr:
        candidates.append(("media2", media2_xaddr))
    if not candidates and service_url:
        parsed = urllib.parse.urlparse(service_url)
        if parsed.scheme and parsed.netloc:
            candidates.append(("media", f"{parsed.scheme}://{parsed.netloc}/onvif/media_service"))
    return candidates


def fetch_onvif_profiles(
    service_url: str,
    username: str | None,
    password: str | None,
    timeout_sec: float,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    metadata = metadata or {}
    profiles: list[dict[str, Any]] = []

    for service_kind, media_url in _media_service_candidates(service_url, metadata):
        action_ns = ONVIF_MEDIA_NS if service_kind == "media" else ONVIF_MEDIA2_NS
        get_profiles_body = (
            "<trt:GetProfiles/>" if service_kind == "media" else "<tr2:GetProfiles/>"
        )
        try:
            root = onvif_soap_call(
                media_url,
                f"{action_ns}/GetProfiles",
                get_profiles_body,
                username,
                password,
                timeout_sec,
            )
        except Exception:
            continue

        response = root.find(
            ".//trt:GetProfilesResponse", NS
        ) or root.find(".//tr2:GetProfilesResponse", NS)
        if response is None:
            continue

        for index, profile in enumerate(list(response), start=1):
            if not isinstance(profile.tag, str):
                continue
            token = profile.attrib.get("token") or profile.attrib.get("fixed") or f"profile-{index}"
            name = _text(next((child for child in profile if _local_name(child.tag) == "Name"), None))

            width = 0
            height = 0
            video_encoder = next(
                (child for child in profile.iter() if _local_name(child.tag) == "VideoEncoderConfiguration"),
                None,
            )
            if video_encoder is not None:
                resolution = next(
                    (child for child in video_encoder.iter() if _local_name(child.tag) == "Resolution"),
                    None,
                )
                if resolution is not None:
                    width = int(_text(next((child for child in resolution if _local_name(child.tag) == "Width"), None)) or 0)
                    height = int(_text(next((child for child in resolution if _local_name(child.tag) == "Height"), None)) or 0)

            stream_uri = ""
            try:
                uri_root = onvif_soap_call(
                    media_url,
                    f"{action_ns}/GetStreamUri",
                    (
                        "<trt:GetStreamUri>"
                        "<trt:StreamSetup>"
                        "<tt:Stream>RTP-Unicast</tt:Stream>"
                        "<tt:Transport><tt:Protocol>RTSP</tt:Protocol></tt:Transport>"
                        "</trt:StreamSetup>"
                        f"<trt:ProfileToken>{token}</trt:ProfileToken>"
                        "</trt:GetStreamUri>"
                        if service_kind == "media"
                        else
                        "<tr2:GetStreamUri>"
                        "<tr2:Protocol>RTSP</tr2:Protocol>"
                        f"<tr2:ProfileToken>{token}</tr2:ProfileToken>"
                        "</tr2:GetStreamUri>"
                    ),
                    username,
                    password,
                    timeout_sec,
                )
                uri_node = next(
                    (
                        child
                        for child in uri_root.iter()
                        if _local_name(child.tag) == "Uri"
                    ),
                    None,
                )
                stream_uri = _text(uri_node)
            except Exception:
                stream_uri = ""

            profiles.append(
                {
                    "token": token,
                    "name": name or f"profile-{index}",
                    "width": width,
                    "height": height,
                    "rtsp_url": stream_uri,
                    "service_url": media_url,
                    "source": service_kind,
                }
            )

        if profiles:
            break

    return profiles


def _manual_onvif_device_candidates(
    hosts: list[str], onvif_ports: list[int], timeout_sec: float, port_probe: DiscoveryProbeFn
) -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    seen: set[str] = set()
    for host in hosts:
        for port in onvif_ports:
            if not port_probe(f"{host}:{port}", timeout_sec):
                continue
            service_url = f"http://{host}:{port}/onvif/device_service"
            if service_url in seen:
                continue
            seen.add(service_url)
            devices.append(
                {
                    "host": host,
                    "port": port,
                    "xaddr": service_url,
                    "xaddrs": [service_url],
                    "scopes": [],
                    "urn": "",
                    "types": "",
                    "discovery": "tcp-fallback",
                }
            )
    return devices


def _suggest_camera_config(
    *,
    candidate: dict[str, Any],
    hardware_profile: dict[str, Any],
    estimated_total_cameras: int,
) -> dict[str, Any]:
    resolution = candidate.get("resolution", {}) if isinstance(candidate.get("resolution"), dict) else {}
    width = int(resolution.get("width", 0) or 0)
    height = int(resolution.get("height", 0) or 0)
    fps = float(candidate.get("fps", 0.0) or 0.0)
    has_audio = bool(candidate.get("has_audio", False))
    accelerator = str(hardware_profile.get("decode_acceleration", "software") or "software")
    default_detect_fps = int(
        hardware_profile.get("recommendation", {}).get("default_detect_fps", 5) or 5
    )

    pixel_count = max(1, width * height)
    if pixel_count >= 1920 * 1080:
        recommended_detect_fps = min(default_detect_fps, 5 if accelerator == "software" else 8)
    elif pixel_count >= 1280 * 720:
        recommended_detect_fps = min(default_detect_fps + 1, 6 if accelerator == "software" else 10)
    else:
        recommended_detect_fps = min(default_detect_fps + 2, 8 if accelerator == "software" else 12)

    if estimated_total_cameras >= 12:
        recommended_detect_fps = max(3, recommended_detect_fps - 2)
    elif estimated_total_cameras >= 6:
        recommended_detect_fps = max(4, recommended_detect_fps - 1)

    if fps > 0:
        recommended_detect_fps = min(recommended_detect_fps, int(max(1.0, fps)))

    hwaccel_args = {
        "nvidia": "preset-nvidia",
        "vaapi": "preset-vaapi",
        "software": "",
    }.get(accelerator, "")

    source_type = str(candidate.get("source_type", "camera") or "camera")
    recommendation_reason = "camera_dedicada"
    if source_type == "nvr_channel":
        recommendation_reason = "canal_de_nvr"

    return {
        "detect_fps": int(recommended_detect_fps),
        "record_enabled": True,
        "audio_enabled": has_audio,
        "hwaccel_args": hwaccel_args,
        "input_preset": "preset-rtsp-generic",
        "reason": recommendation_reason,
    }


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
    onvif_discover_fn: OnvifDiscoverFn | None = None,
    onvif_device_fn: OnvifDeviceFn | None = None,
    onvif_profiles_fn: OnvifProfilesFn | None = None,
) -> dict[str, Any]:
    hosts = expand_scan_targets(targets, max_hosts=max_hosts)
    rtsp_ports = rtsp_ports or list(DEFAULT_RTSP_PORTS)
    onvif_ports = onvif_ports or list(DEFAULT_ONVIF_PORTS)
    profiles = profiles or list(DEFAULT_DISCOVERY_PROFILES)

    candidates: list[dict[str, Any]] = []
    open_hosts: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    hardware_profile = build_hardware_profile()

    onvif_discover_fn = onvif_discover_fn or ws_discover_onvif_devices
    onvif_device_fn = onvif_device_fn or fetch_onvif_device_metadata
    onvif_profiles_fn = onvif_profiles_fn or fetch_onvif_profiles

    discovered_onvif = onvif_discover_fn(targets=targets, timeout_sec=timeout_sec)
    fallback_onvif = _manual_onvif_device_candidates(
        hosts, onvif_ports, timeout_sec, port_probe
    )
    onvif_devices_by_host: dict[str, dict[str, Any]] = {}
    for device in [*discovered_onvif, *fallback_onvif]:
        host = str(device.get("host") or "")
        if not host or host in onvif_devices_by_host:
            continue
        onvif_devices_by_host[host] = device

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
                "onvif_discovered": host in onvif_devices_by_host,
            }
        )

        onvif_device = onvif_devices_by_host.get(host)
        onvif_metadata: dict[str, Any] = {}
        onvif_profiles: list[dict[str, Any]] = []
        if onvif_device and onvif_device.get("xaddr"):
            try:
                onvif_metadata = onvif_device_fn(
                    str(onvif_device["xaddr"]), username, password, timeout_sec
                )
            except Exception:
                onvif_metadata = {}
            try:
                onvif_profiles = onvif_profiles_fn(
                    str(onvif_device["xaddr"]),
                    username,
                    password,
                    timeout_sec,
                    onvif_metadata,
                )
            except TypeError:
                onvif_profiles = onvif_profiles_fn(
                    str(onvif_device["xaddr"]), username, password, timeout_sec
                )
            except Exception:
                onvif_profiles = []

        for index, profile in enumerate(onvif_profiles, start=1):
            rtsp_url = str(profile.get("rtsp_url") or "")
            if not rtsp_url or rtsp_url in seen_urls:
                continue

            stream = stream_probe(rtsp_url, ffprobe_path, timeout_sec) or {
                "width": int(profile.get("width", 0) or 0),
                "height": int(profile.get("height", 0) or 0),
                "codec": None,
                "fps": 0.0,
                "has_audio": False,
                "audio_codec": None,
            }
            seen_urls.add(rtsp_url)

            width = int(stream.get("width", 0) or 0)
            height = int(stream.get("height", 0) or 0)
            channel = index if len(onvif_profiles) > 1 else None
            candidate = {
                "id": f"{host}-onvif-{profile.get('token') or index}",
                "host": host,
                "port": int(onvif_device.get("port", 0) or 0),
                "profile": "onvif",
                "channel": channel,
                "source_type": "nvr_channel" if channel is not None else "camera",
                "rtsp_url": rtsp_url,
                "resolution": {
                    "width": width,
                    "height": height,
                },
                "codec": stream.get("codec"),
                "fps": float(stream.get("fps", 0.0) or 0.0),
                "has_audio": bool(stream.get("has_audio", False)),
                "audio_codec": stream.get("audio_codec"),
                "onvif_reachable": True,
                "onvif": {
                    "service_url": onvif_device.get("xaddr"),
                    "metadata": onvif_metadata,
                    "profile_token": profile.get("token"),
                    "profile_name": profile.get("name"),
                    "stream_source": profile.get("source"),
                },
                "suggested_camera_name": (
                    f"nvr_{host.replace('.', '_')}_ch{channel:02d}"
                    if channel is not None
                    else (
                        f"{str(onvif_metadata.get('model') or 'cam').strip().lower().replace(' ', '_')}_{host.replace('.', '_')}"
                    )
                ),
                "discovery_method": "onvif",
            }
            candidate["recommended_config"] = _suggest_camera_config(
                candidate=candidate,
                hardware_profile=hardware_profile,
                estimated_total_cameras=max(1, len(onvif_profiles)),
            )
            candidates.append(candidate)
            if len(candidates) >= max_candidates:
                break

        if len(candidates) >= max_candidates:
            break

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
                    candidate = {
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
                        "fps": float(stream.get("fps", 0.0) or 0.0),
                        "has_audio": bool(stream.get("has_audio", False)),
                        "audio_codec": stream.get("audio_codec"),
                        "onvif_reachable": bool(open_onvif_ports),
                        "suggested_camera_name": suggested_name,
                        "discovery_method": "rtsp-pattern",
                    }
                    if onvif_device:
                        candidate["onvif"] = {
                            "service_url": onvif_device.get("xaddr"),
                            "metadata": onvif_metadata,
                        }
                    candidate["recommended_config"] = _suggest_camera_config(
                        candidate=candidate,
                        hardware_profile=hardware_profile,
                        estimated_total_cameras=max(1, len(candidates) + 1),
                    )
                    candidates.append(candidate)
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
        "hardware_profile": hardware_profile,
        "targets_scanned": hosts,
        "reachable_hosts": open_hosts,
        "onvif_devices": list(onvif_devices_by_host.values()),
        "candidates": candidates,
        "summary": {
            "hosts_scanned": len(hosts),
            "hosts_reachable": len(open_hosts),
            "onvif_devices_found": len(onvif_devices_by_host),
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
        recommended = (
            item.get("recommended_config", {})
            if isinstance(item.get("recommended_config"), dict)
            else {}
        )
        audio_enabled = bool(recommended.get("audio_enabled", False))
        if audio_enabled and "audio" not in roles:
            roles.append("audio")

        camera_patch = {
            "enabled": True,
            "detect": {
                "enabled": detect_enabled,
                "fps": int(recommended.get("detect_fps", 5) or 5),
            },
            "record": {
                "enabled": record_enabled,
            },
            "audio": {
                "enabled": audio_enabled,
            },
            "ffmpeg": {
                "hwaccel_args": recommended.get("hwaccel_args", ""),
                "inputs": [
                    {
                        "path": rtsp_url,
                        "roles": roles,
                        "input_args": recommended.get("input_preset", "preset-rtsp-generic"),
                    }
                ]
            },
            "live": {
                "streams": {
                    stream_name: stream_name,
                }
            },
        }

        onvif = item.get("onvif", {}) if isinstance(item.get("onvif"), dict) else {}
        onvif_service = str(onvif.get("service_url") or "")
        if onvif_service:
            parsed = urllib.parse.urlparse(onvif_service)
            camera_patch["onvif"] = {
                "host": parsed.hostname or item.get("host", ""),
                "port": parsed.port or 80,
            }

        cameras_patch[camera_name] = camera_patch
        go2rtc_streams[stream_name] = rtsp_url

    patch: dict[str, Any] = {}
    if cameras_patch:
        patch["cameras"] = cameras_patch
    if go2rtc_streams:
        patch["go2rtc"] = {"streams": go2rtc_streams}
    return patch
