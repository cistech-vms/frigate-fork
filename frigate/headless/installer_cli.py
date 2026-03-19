from __future__ import annotations

import argparse
import getpass
import ipaddress
import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


def _safe_import_psutil():
    try:
        import psutil  # type: ignore

        return psutil
    except Exception:
        return None


def _normalize_base_url(base_url: str) -> str:
    value = (base_url or "").strip().rstrip("/")
    if not value:
        raise ValueError("base_url is required")
    if not value.startswith(("http://", "https://")):
        value = f"http://{value}"
    return value


def _parse_extra_headers(items: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in items:
        if ":" not in item:
            raise ValueError(f"Invalid header format: {item}")
        key, value = item.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError("Header name cannot be empty")
        headers[key] = value
    return headers


def _mask_secret(value: str | None) -> str:
    return "configured" if value else "not set"


def _format_gib(value: int | float) -> str:
    return f"{float(value) / (1024 ** 3):.1f} GiB"


def _format_bytes(value: int | float) -> str:
    amount = float(value)
    if amount <= 0:
        return "0 B"
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    index = 0
    while amount >= 1024 and index < len(units) - 1:
        amount /= 1024
        index += 1
    return f"{amount:.1f} {units[index]}"


def _private_networks_from_interfaces(
    interface_map: dict[str, list[dict[str, str]]],
) -> list[str]:
    excluded_prefixes = (
        "lo",
        "docker",
        "br-",
        "veth",
        "cni",
        "flannel",
        "tailscale",
        "tun",
        "wg",
    )
    networks: list[str] = []

    def add_network(cidr: str) -> None:
        if cidr not in networks:
            networks.append(cidr)

    for name, addresses in interface_map.items():
        if name.startswith(excluded_prefixes):
            continue
        for item in addresses:
            address_raw = str(item.get("address") or "").strip()
            netmask_raw = str(item.get("netmask") or "").strip()
            if not address_raw or not netmask_raw:
                continue
            try:
                address = ipaddress.ip_address(address_raw)
            except ValueError:
                continue
            if not isinstance(address, ipaddress.IPv4Address):
                continue
            if (
                address.is_loopback
                or address.is_link_local
                or address.is_multicast
                or address.is_unspecified
                or not address.is_private
            ):
                continue
            try:
                network = ipaddress.ip_network(f"{address_raw}/{netmask_raw}", strict=False)
            except ValueError:
                continue
            add_network(str(network))

    return networks


def suggest_scan_targets() -> list[str]:
    psutil = _safe_import_psutil()
    if psutil is None or not hasattr(psutil, "net_if_addrs"):
        return []

    interface_map: dict[str, list[dict[str, str]]] = {}
    try:
        raw = psutil.net_if_addrs()
    except Exception:
        return []

    for name, addresses in raw.items():
        entries: list[dict[str, str]] = []
        for item in addresses:
            family = getattr(item, "family", None)
            if family != socket.AF_INET:
                continue
            entries.append(
                {
                    "address": str(getattr(item, "address", "") or ""),
                    "netmask": str(getattr(item, "netmask", "") or ""),
                }
            )
        if entries:
            interface_map[name] = entries

    return _private_networks_from_interfaces(interface_map)


def _parse_bool_prompt(value: str, default: bool) -> bool:
    normalized = (value or "").strip().lower()
    if not normalized:
        return default
    if normalized in {"y", "yes", "s", "sim", "1", "true"}:
        return True
    if normalized in {"n", "no", "nao", "não", "0", "false"}:
        return False
    raise ValueError("Resposta invalida")


def parse_candidate_selection(selection: str, candidates: list[dict[str, Any]]) -> list[str]:
    normalized = (selection or "").strip().lower()
    if not normalized or normalized == "all":
        return [str(item.get("id")) for item in candidates if item.get("id")]

    ids: list[str] = []
    max_index = len(candidates)
    tokens = [token.strip() for token in normalized.split(",") if token.strip()]
    for token in tokens:
        if "-" in token:
            start_raw, end_raw = token.split("-", 1)
            start = int(start_raw)
            end = int(end_raw)
            if start > end:
                start, end = end, start
            if start < 1 or end > max_index:
                raise ValueError("Faixa fora da lista de candidatos")
            for index in range(start, end + 1):
                candidate_id = str(candidates[index - 1].get("id") or "")
                if candidate_id and candidate_id not in ids:
                    ids.append(candidate_id)
            continue

        index = int(token)
        if index < 1 or index > max_index:
            raise ValueError("Indice fora da lista de candidatos")
        candidate_id = str(candidates[index - 1].get("id") or "")
        if candidate_id and candidate_id not in ids:
            ids.append(candidate_id)

    return ids


def _scan_payload_from_args(
    args: argparse.Namespace,
    *,
    username: str | None = None,
    password: str | None = None,
) -> dict[str, Any]:
    targets = list(args.targets or [])
    return {
        "targets": targets,
        "username": username if username is not None else args.username,
        "password": password if password is not None else args.password,
        "rtsp_ports": list(args.rtsp_ports),
        "onvif_ports": list(args.onvif_ports),
        "profiles": list(args.profiles),
        "max_hosts": args.max_hosts,
        "max_channels": args.max_channels,
        "max_candidates": args.max_candidates,
        "timeout_sec": args.scan_timeout_sec,
    }


@dataclass
class InstallerApiError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return f"HTTP {self.status_code}: {self.detail}"


class InstallerApiClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_sec: float = 30.0,
        headers: dict[str, str] | None = None,
        opener: urllib.request.OpenerDirector | None = None,
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.timeout_sec = max(1.0, float(timeout_sec))
        self.headers = headers or {}
        self.opener = opener or urllib.request.build_opener()

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = urllib.parse.urljoin(f"{self.base_url}/", path.lstrip("/"))
        body = None
        headers = {
            "Accept": "application/json",
            **self.headers,
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with self.opener.open(request, timeout=self.timeout_sec) as response:
                raw = response.read().decode("utf-8") if response else ""
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            detail = raw.strip() or exc.reason
            try:
                payload = json.loads(raw)
                detail = json.dumps(payload, ensure_ascii=False)
            except Exception:
                pass
            raise InstallerApiError(exc.code, detail) from exc
        except urllib.error.URLError as exc:
            raise InstallerApiError(0, str(exc.reason)) from exc

    def get_status(self) -> dict[str, Any]:
        return self._request("GET", "/install/status")

    def get_hardware_profile(self) -> dict[str, Any]:
        return self._request("POST", "/install/hardware/profile", {})

    def scan(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/install/discovery/scan", payload)

    def get_candidates(self) -> dict[str, Any]:
        return self._request("GET", "/install/discovery/candidates")

    def connect(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/install/discovery/connect", payload)


def _print_section(title: str) -> None:
    print(f"\n== {title} ==")


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _display_status(payload: dict[str, Any]) -> None:
    _print_section("Status do Instalador")
    print(f"Habilitado: {'sim' if payload.get('enabled') else 'não'}")
    print(f"Cameras configuradas: {payload.get('cameras_configured', 0)}")
    print(f"Restart pendente: {'sim' if payload.get('pending_restart') else 'não'}")
    summary = payload.get("last_scan_summary", {}) if isinstance(payload.get("last_scan_summary"), dict) else {}
    if summary:
        print(
            "Ultimo scan: "
            f"hosts={summary.get('hosts_scanned', 0)}, "
            f"alcancados={summary.get('hosts_reachable', 0)}, "
            f"candidatos={summary.get('candidates_found', 0)}"
        )


def _display_profile(payload: dict[str, Any]) -> None:
    _print_section("Perfil do Hardware")
    node = payload.get("node", {}) if isinstance(payload.get("node"), dict) else {}
    recommendation = (
        payload.get("recommendation", {})
        if isinstance(payload.get("recommendation"), dict)
        else {}
    )
    profiles = recommendation.get("profiles", {}) if isinstance(recommendation.get("profiles"), dict) else {}
    notes = recommendation.get("notes", []) if isinstance(recommendation.get("notes"), list) else []

    print(f"Host: {node.get('hostname', 'unknown')}")
    print(
        f"CPU: {node.get('logical_cpus', '?')} logicas / "
        f"{node.get('physical_cpus', '?')} fisicas"
    )
    print(
        "Memoria efetiva: "
        f"{_format_gib(node.get('effective_mem_bytes', 0) or 0)}"
    )
    print(f"Disco livre: {_format_bytes(node.get('disk_free_bytes', 0) or 0)}")
    print(f"Decode: {payload.get('decode_acceleration', 'software')}")
    print(f"Tier sugerido: {recommendation.get('tier', 'edge_basic')}")
    print(
        "Capacidade estimada: "
        f"720p@5={profiles.get('720p_5fps', 0)}, "
        f"1080p@5={profiles.get('1080p_5fps', 0)}, "
        f"1080p@10={profiles.get('1080p_10fps', 0)}"
    )
    if notes:
        print("Observacoes:")
        for note in notes:
            print(f"- {note}")


def _display_scan(payload: dict[str, Any]) -> None:
    _print_section("Resumo da Descoberta")
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    print(f"Hosts escaneados: {summary.get('hosts_scanned', 0)}")
    print(f"Hosts alcancados: {summary.get('hosts_reachable', 0)}")
    print(f"Devices ONVIF: {summary.get('onvif_devices_found', 0)}")
    print(f"Candidatos validados: {summary.get('candidates_found', 0)}")

    candidates = payload.get("candidates", []) if isinstance(payload.get("candidates"), list) else []
    if not candidates:
        print("\nNenhum candidato encontrado.")
        prompt = payload.get("connect_prompt", {}) if isinstance(payload.get("connect_prompt"), dict) else {}
        message = prompt.get("message")
        if message:
            print(message)
        return

    _print_section("Candidatos Encontrados")
    for index, candidate in enumerate(candidates, start=1):
        resolution = (
            candidate.get("resolution", {})
            if isinstance(candidate.get("resolution"), dict)
            else {}
        )
        recommended = (
            candidate.get("recommended_config", {})
            if isinstance(candidate.get("recommended_config"), dict)
            else {}
        )
        onvif = candidate.get("onvif", {}) if isinstance(candidate.get("onvif"), dict) else {}
        metadata = onvif.get("metadata", {}) if isinstance(onvif.get("metadata"), dict) else {}
        print(
            f"[{index}] {candidate.get('suggested_camera_name', candidate.get('id', 'camera'))} "
            f"| host={candidate.get('host')} "
            f"| origem={candidate.get('discovery_method', 'unknown')}"
        )
        print(
            "    "
            f"{resolution.get('width', 0)}x{resolution.get('height', 0)} "
            f"| codec={candidate.get('codec') or '-'} "
            f"| fps={candidate.get('fps', 0)} "
            f"| audio={'sim' if candidate.get('has_audio') else 'não'}"
        )
        if metadata:
            print(
                "    "
                f"onvif={metadata.get('manufacturer', '-')}/{metadata.get('model', '-')}"
            )
        print(
            "    "
            f"sugestao: detect_fps={recommended.get('detect_fps', 5)}, "
            f"record={'on' if recommended.get('record_enabled', True) else 'off'}, "
            f"audio={'on' if recommended.get('audio_enabled') else 'off'}, "
            f"hwaccel={recommended.get('hwaccel_args') or 'auto'}"
        )


def _display_connect_result(payload: dict[str, Any]) -> None:
    _print_section("Configuracao Preparada")
    print(payload.get("message", "Configuracao staged com sucesso."))
    print(f"Tenant: {payload.get('tenant_id', 'default')}")
    print(f"Restart pendente: {'sim' if payload.get('pending_restart') else 'não'}")
    cameras = payload.get("cameras", []) if isinstance(payload.get("cameras"), list) else []
    streams = payload.get("go2rtc_streams", []) if isinstance(payload.get("go2rtc_streams"), list) else []
    if cameras:
        print("Cameras:")
        for item in cameras:
            print(f"- {item}")
    if streams:
        print("Streams go2rtc:")
        for item in streams:
            print(f"- {item}")


def _prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    if value:
        return value
    return default or ""


def _build_client(args: argparse.Namespace) -> InstallerApiClient:
    headers = _parse_extra_headers(list(args.header or []))
    return InstallerApiClient(
        base_url=args.base_url,
        timeout_sec=args.request_timeout_sec,
        headers=headers,
    )


def _command_status(args: argparse.Namespace) -> int:
    payload = _build_client(args).get_status()
    if args.json:
        _print_json(payload)
    else:
        _display_status(payload)
    return 0


def _command_profile(args: argparse.Namespace) -> int:
    payload = _build_client(args).get_hardware_profile()
    if args.json:
        _print_json(payload)
    else:
        _display_profile(payload)
    return 0


def _command_scan(args: argparse.Namespace) -> int:
    payload = _build_client(args).scan(_scan_payload_from_args(args))
    if args.json:
        _print_json(payload)
    else:
        _display_scan(payload)
    return 0


def _command_connect(args: argparse.Namespace) -> int:
    payload = {
        "candidate_ids": list(args.candidate_id or []),
        "connect_all": bool(args.all),
        "camera_name_prefix": args.camera_name_prefix,
        "detect_enabled": not args.disable_detect,
        "record_enabled": not args.disable_record,
    }
    result = _build_client(args).connect(payload)
    if args.json:
        _print_json(result)
    else:
        _display_connect_result(result)
    return 0


def _command_wizard(args: argparse.Namespace) -> int:
    client = _build_client(args)

    status = client.get_status()
    _display_status(status)
    if int(status.get("cameras_configured", 0) or 0) > 0:
        print("\nO assistente so pode ser usado antes da configuracao inicial das cameras.")
        return 1

    profile = client.get_hardware_profile()
    _display_profile(profile)

    suggestions = suggest_scan_targets()
    default_targets = ",".join(suggestions[:3]) if suggestions else ""
    print("\nRedes sugeridas para scan:")
    if suggestions:
        for item in suggestions[:5]:
            print(f"- {item}")
    else:
        print("- nenhuma rede privada local detectada automaticamente")
        print("- informe manualmente uma rede, faixa ou host")

    targets_raw = _prompt(
        "Alvos para o scan (separe por virgula)",
        default_targets or "192.168.1.0/24",
    )
    username = _prompt("Usuario RTSP/ONVIF", args.username or "")
    password = args.password or ""
    if username and not password:
        password = getpass.getpass("Senha RTSP/ONVIF: ")

    scan_args = argparse.Namespace(**vars(args))
    scan_args.targets = [item.strip() for item in targets_raw.split(",") if item.strip()]
    payload = _scan_payload_from_args(scan_args, username=username or None, password=password or None)

    print("\nExecutando descoberta de cameras e NVR...")
    scan_result = client.scan(payload)
    _display_scan(scan_result)

    candidates = scan_result.get("candidates", []) if isinstance(scan_result.get("candidates"), list) else []
    if not candidates:
        print("\nNenhuma camera validada. Revise rede, credenciais e portas antes de tentar novamente.")
        return 1

    selection = _prompt(
        "Selecione candidatos por indice (ex: 1,2,4-6) ou 'all'",
        "all",
    )
    try:
        candidate_ids = parse_candidate_selection(selection, candidates)
    except ValueError as exc:
        print(f"\nSelecao invalida: {exc}")
        return 1

    camera_name_prefix = _prompt("Prefixo dos nomes das cameras", args.camera_name_prefix)
    try:
        detect_enabled = _parse_bool_prompt(
            _prompt("Habilitar detect?", "s" if not args.disable_detect else "n"),
            default=not args.disable_detect,
        )
        record_enabled = _parse_bool_prompt(
            _prompt("Habilitar record?", "s" if not args.disable_record else "n"),
            default=not args.disable_record,
        )
    except ValueError as exc:
        print(f"\nEntrada invalida: {exc}")
        return 1

    print("\nResumo da confirmacao:")
    print(f"- candidatos selecionados: {len(candidate_ids)}")
    print(f"- prefixo: {camera_name_prefix}")
    print(f"- detect: {'on' if detect_enabled else 'off'}")
    print(f"- record: {'on' if record_enabled else 'off'}")

    try:
        confirmed = _parse_bool_prompt(_prompt("Aplicar staging agora?", "s"), default=True)
    except ValueError as exc:
        print(f"\nEntrada invalida: {exc}")
        return 1
    if not confirmed:
        print("\nOperacao cancelada.")
        return 1

    result = client.connect(
        {
            "candidate_ids": candidate_ids,
            "connect_all": False,
            "camera_name_prefix": camera_name_prefix,
            "detect_enabled": detect_enabled,
            "record_enabled": record_enabled,
        }
    )
    _display_connect_result(result)
    print("\nProximo passo: reiniciar o Frigate para aplicar as cameras staged.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="frigate install",
        description="Assistente headless de instalacao do Frigate.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("FRIGATE_INSTALL_BASE_URL", "http://127.0.0.1:5001"),
        help="Base URL da API headless do Frigate.",
    )
    parser.add_argument(
        "--request-timeout-sec",
        type=float,
        default=float(os.getenv("FRIGATE_INSTALL_TIMEOUT_SEC", "30")),
        help="Timeout HTTP em segundos.",
    )
    parser.add_argument(
        "--header",
        action="append",
        default=[],
        help="Header adicional no formato 'Nome: valor'.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Mostra a resposta crua em JSON.",
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Mostra o status do instalador.")
    subparsers.add_parser("profile", help="Mostra o perfil de hardware.")

    scan = subparsers.add_parser("scan", help="Executa o scan de cameras e NVR.")
    scan.add_argument("targets", nargs="*", default=["192.168.1.0/24"])
    scan.add_argument("--username", default=None)
    scan.add_argument("--password", default=None)
    scan.add_argument("--rtsp-port", dest="rtsp_ports", action="append", type=int, default=[554, 8554])
    scan.add_argument("--onvif-port", dest="onvif_ports", action="append", type=int, default=[80, 8000, 8080, 8899])
    scan.add_argument(
        "--profile",
        dest="profiles",
        action="append",
        default=["hikvision", "dahua", "reolink", "uniview", "generic"],
    )
    scan.add_argument("--max-hosts", type=int, default=256)
    scan.add_argument("--max-channels", type=int, default=16)
    scan.add_argument("--max-candidates", type=int, default=128)
    scan.add_argument("--scan-timeout-sec", type=float, default=2.0)

    connect = subparsers.add_parser("connect", help="Conecta candidatos descobertos.")
    connect.add_argument("--candidate-id", action="append", default=[])
    connect.add_argument("--all", action="store_true")
    connect.add_argument("--camera-name-prefix", default="cam")
    connect.add_argument("--disable-detect", action="store_true")
    connect.add_argument("--disable-record", action="store_true")

    wizard = subparsers.add_parser("wizard", help="Executa o setup assistido no terminal.")
    wizard.add_argument("--username", default=None)
    wizard.add_argument("--password", default=None)
    wizard.add_argument("--camera-name-prefix", default="cam")
    wizard.add_argument("--disable-detect", action="store_true")
    wizard.add_argument("--disable-record", action="store_true")
    wizard.add_argument("--max-hosts", type=int, default=256)
    wizard.add_argument("--max-channels", type=int, default=16)
    wizard.add_argument("--max-candidates", type=int, default=128)
    wizard.add_argument("--scan-timeout-sec", type=float, default=2.0)
    wizard.add_argument("--rtsp-port", dest="rtsp_ports", action="append", type=int, default=[554, 8554])
    wizard.add_argument("--onvif-port", dest="onvif_ports", action="append", type=int, default=[80, 8000, 8080, 8899])
    wizard.add_argument(
        "--profile",
        dest="profiles",
        action="append",
        default=["hikvision", "dahua", "reolink", "uniview", "generic"],
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "wizard"

    try:
        if command == "status":
            return _command_status(args)
        if command == "profile":
            return _command_profile(args)
        if command == "scan":
            return _command_scan(args)
        if command == "connect":
            return _command_connect(args)
        return _command_wizard(args)
    except InstallerApiError as exc:
        print(f"\nFalha no instalador: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperacao interrompida pelo usuario.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
