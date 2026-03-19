from __future__ import annotations

import copy
import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from frigate.headless.runtime_config import CanaryPolicy

logger = logging.getLogger(__name__)

TransportFn = Callable[[str, str, dict[str, str], dict[str, Any] | None, float], tuple[int, dict[str, Any], dict[str, str]]]
HotReloadFn = Callable[[dict[str, Any], Any], Any]


def _now() -> int:
    return int(time.time())


def _default_runtime() -> dict[str, Any]:
    return {
        "enabled": False,
        "connected": False,
        "mode": "disabled",
        "edge_id": "",
        "config_version": 0,
        "etag": "",
        "last_sync_ts": 0,
        "last_apply_ts": 0,
        "last_error": "",
        "auth": {
            "mode": "",
            "status": "not_configured",
            "expires_at": 0,
            "last_auth_ts": 0,
        },
        "license": {
            "status": "unknown",
            "valid": False,
            "checked_at": 0,
            "expires_at": 0,
            "grace_until": 0,
            "reason": "not_configured",
        },
        "metrics": {
            "auth_success": 0,
            "auth_failed": 0,
            "sync_success": 0,
            "sync_failed": 0,
            "config_applied": 0,
            "config_unchanged": 0,
            "rollback_applied": 0,
        },
        "last_known_good": {
            "runtime_patch": {},
            "config_version": 0,
            "etag": "",
            "applied_at": 0,
        },
        "audit": [],
    }


def _merge_runtime(base: dict[str, Any], persisted: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in persisted.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


class CmsRemoteManager:
    def __init__(
        self,
        *,
        settings: Any,
        state_store: Any,
        runtime_store: Any,
        stats_provider: Callable[[], dict[str, Any]],
        runtime_tenant: str,
        node_id: str,
        frigate_version: str,
        transport: TransportFn | None = None,
        on_runtime_patch_applied: HotReloadFn | None = None,
    ) -> None:
        self.settings = settings
        self.state_store = state_store
        self.runtime_store = runtime_store
        self.stats_provider = stats_provider
        self.runtime_tenant = runtime_tenant or "default"
        self.node_id = node_id
        self.frigate_version = frigate_version
        self.transport = transport
        self.on_runtime_patch_applied = on_runtime_patch_applied
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, name="cms_remote_sync", daemon=True)
        self._session: dict[str, Any] = {"access_token": "", "refresh_token": "", "expires_at": 0}
        persisted = state_store.cms_runtime() if hasattr(state_store, "cms_runtime") else {}
        self._runtime = _merge_runtime(_default_runtime(), persisted if isinstance(persisted, dict) else {})
        self._runtime["enabled"] = bool(getattr(settings, "cms_enabled", False))
        if self._runtime["enabled"]:
            self._runtime["mode"] = "booting"
            self._runtime["auth"]["mode"] = str(getattr(settings, "cms_auth_mode", "token"))

    def start(self) -> None:
        if not self._runtime.get("enabled", False):
            self._runtime["mode"] = "disabled"
            self._persist()
            return
        self.sync_once(force=True, reason="startup")
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def status(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._runtime)

    def sync_once(self, *, force: bool = False, reason: str = "manual") -> dict[str, Any]:
        if not self._runtime.get("enabled", False):
            snapshot = self.status()
            snapshot["mode"] = "disabled"
            return snapshot

        with self._lock:
            self._runtime["mode"] = "syncing"
            self._runtime["last_error"] = ""

        try:
            self._ensure_authenticated()
            self._ensure_edge_registered()
            license_state = self._validate_license()
            if not self._is_license_allowed(license_state):
                with self._lock:
                    self._runtime["connected"] = False
                    self._runtime["mode"] = "license_blocked"
                    self._runtime["metrics"]["sync_failed"] += 1
                    self._runtime["last_sync_ts"] = _now()
                self._persist()
                return self.status()

            result = self._fetch_remote_config(force=force)
            if result.get("status") == "not_modified":
                with self._lock:
                    self._runtime["connected"] = True
                    self._runtime["mode"] = "ready"
                    self._runtime["last_sync_ts"] = _now()
                    self._runtime["metrics"]["sync_success"] += 1
                    self._runtime["metrics"]["config_unchanged"] += 1
                self._persist()
                return self.status()

            try:
                apply_result = self._apply_remote_config(result)
            except Exception:
                self._restore_last_known_good()
                raise
            with self._lock:
                self._runtime["connected"] = True
                self._runtime["mode"] = "ready"
                self._runtime["last_sync_ts"] = _now()
                self._runtime["last_apply_ts"] = _now()
                self._runtime["config_version"] = int(result.get("config_version", 0) or 0)
                self._runtime["etag"] = str(result.get("etag", "") or "")
                self._runtime["metrics"]["sync_success"] += 1
                self._runtime["metrics"]["config_applied"] += int(bool(apply_result.get("applied", False)))
                self._append_audit(
                    {
                        "ts": _now(),
                        "event": "config_applied",
                        "config_version": self._runtime["config_version"],
                        "etag": self._runtime["etag"],
                        "reason": reason,
                    }
                )
            self._persist()
            return self.status()
        except Exception as exc:
            with self._lock:
                self._runtime["connected"] = False
                self._runtime["mode"] = "degraded"
                self._runtime["last_error"] = str(exc)
                self._runtime["last_sync_ts"] = _now()
                self._runtime["metrics"]["sync_failed"] += 1
                self._append_audit(
                    {
                        "ts": _now(),
                        "event": "sync_failed",
                        "error": str(exc),
                        "reason": reason,
                    }
                )
            self._persist()
            return self.status()

    def enrich_readiness(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        if not self._runtime.get("enabled", False):
            return snapshot

        enriched = copy.deepcopy(snapshot)
        checks = enriched.setdefault("checks", {})
        reasons = enriched.setdefault("reasons", [])
        warnings = enriched.setdefault("warnings", [])
        status = self.status()

        checks["cms_enabled"] = True
        checks["cms_connected"] = bool(status.get("connected", False))
        checks["cms_mode"] = status.get("mode", "unknown")
        checks["cms_license_status"] = status.get("license", {}).get("status", "unknown")
        checks["cms_last_sync_ts"] = int(status.get("last_sync_ts", 0) or 0)

        if not status.get("connected", False):
            warnings.append("cms_disconnected")

        license_state = status.get("license", {})
        if not self._is_license_allowed(license_state):
            reasons.append("cms_license_invalid")

        if checks["cms_last_sync_ts"] <= 0:
            warnings.append("cms_never_synced")
        else:
            max_age = max(60, int(getattr(self.settings, "cms_sync_interval_sec", 60)) * 4)
            age = max(0, _now() - checks["cms_last_sync_ts"])
            checks["cms_last_sync_age_sec"] = age
            if age > max_age:
                warnings.append("cms_config_stale")

        if reasons:
            enriched["ready"] = False
            enriched["mode"] = "not_ready"
            enriched["write_critical_allowed"] = False
        elif warnings and enriched.get("mode") == "normal":
            enriched["mode"] = "degraded_read_only"
            enriched["write_critical_allowed"] = False
        return enriched

    def _run(self) -> None:
        interval = max(5, int(getattr(self.settings, "cms_sync_interval_sec", 60) or 60))
        while not self._stop_event.wait(interval):
            self.sync_once(reason="periodic")

    def _ensure_authenticated(self) -> None:
        mode = str(getattr(self.settings, "cms_auth_mode", "token"))
        if mode == "token":
            token = str(getattr(self.settings, "cms_token", "") or "")
            if not token:
                raise RuntimeError("cms_missing_token")
            with self._lock:
                self._runtime["metrics"]["auth_success"] += 1
                self._runtime["auth"]["status"] = "active"
                self._runtime["auth"]["last_auth_ts"] = _now()
            return

        now_ts = _now()
        if self._session.get("access_token") and int(self._session.get("expires_at", 0) or 0) > (now_ts + 15):
            with self._lock:
                self._runtime["auth"]["status"] = "active"
                self._runtime["auth"]["expires_at"] = int(self._session.get("expires_at", 0) or 0)
            return

        refreshed = False
        if self._session.get("refresh_token"):
            refreshed = self._refresh_token()
        if not refreshed:
            self._password_login()
        with self._lock:
            self._runtime["metrics"]["auth_success"] += 1
            self._runtime["auth"]["status"] = "active"
            self._runtime["auth"]["last_auth_ts"] = _now()
            self._runtime["auth"]["expires_at"] = int(self._session.get("expires_at", 0) or 0)

    def _password_login(self) -> None:
        username = str(getattr(self.settings, "cms_username", "") or "")
        password = str(getattr(self.settings, "cms_password", "") or "")
        if not username or not password:
            raise RuntimeError("cms_missing_credentials")

        status, body, _ = self._request(
            "POST",
            "/v1/edge/auth/login",
            payload={
                "username": username,
                "password": password,
                "tenant_code": getattr(self.settings, "cms_tenant_code", ""),
                "node_id": self.node_id,
            },
            include_auth=False,
        )
        if status < 200 or status >= 300:
            with self._lock:
                self._runtime["metrics"]["auth_failed"] += 1
                self._runtime["auth"]["status"] = "failed"
            raise RuntimeError(f"cms_login_failed:{status}")
        self._load_session_from_body(body)

    def _refresh_token(self) -> bool:
        refresh_token = str(self._session.get("refresh_token", "") or "")
        if not refresh_token:
            return False
        status, body, _ = self._request(
            "POST",
            "/v1/edge/auth/refresh",
            payload={"refresh_token": refresh_token, "tenant_code": getattr(self.settings, "cms_tenant_code", "")},
            include_auth=False,
        )
        if status < 200 or status >= 300:
            return False
        self._load_session_from_body(body)
        return True

    def _load_session_from_body(self, body: dict[str, Any]) -> None:
        access_token = str(body.get("access_token") or body.get("token") or "")
        refresh_token = str(body.get("refresh_token") or "")
        expires_in = int(body.get("expires_in", 900) or 900)
        if not access_token:
            raise RuntimeError("cms_auth_missing_access_token")
        self._session = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": _now() + max(30, expires_in),
        }

    def _ensure_edge_registered(self) -> None:
        current_edge_id = str(self.status().get("edge_id", "") or "")
        if current_edge_id:
            return
        payload = {
            "tenant_code": getattr(self.settings, "cms_tenant_code", ""),
            "node_id": self.node_id,
            "frigate_version": self.frigate_version,
            "fingerprint": self._fingerprint(),
        }
        status, body, _ = self._request("POST", "/v1/edge/enroll", payload=payload, include_auth=True)
        if status < 200 or status >= 300:
            raise RuntimeError(f"cms_enrollment_failed:{status}")
        edge_id = str(body.get("edge_id") or body.get("id") or "")
        if not edge_id:
            raise RuntimeError("cms_enrollment_missing_edge_id")
        with self._lock:
            self._runtime["edge_id"] = edge_id
            self._append_audit({"ts": _now(), "event": "edge_enrolled", "edge_id": edge_id})
        self._persist()

    def _validate_license(self) -> dict[str, Any]:
        now_ts = _now()
        try:
            status, body, _ = self._request(
                "POST",
                "/v1/edge/license/validate",
                payload={
                    "tenant_code": getattr(self.settings, "cms_tenant_code", ""),
                    "edge_id": self.status().get("edge_id"),
                },
                include_auth=True,
            )
        except Exception:
            status = 0
            body = {}
        if 200 <= status < 300:
            valid = bool(body.get("valid", False))
            expires_at = int(body.get("expires_at", 0) or 0)
            reason = str(body.get("reason", "ok" if valid else "invalid"))
            grace_until = max(
                int(self.status().get("license", {}).get("grace_until", 0) or 0),
                now_ts + int(getattr(self.settings, "cms_license_grace_sec", 900)),
            )
            license_state = {
                "status": "valid" if valid else "invalid",
                "valid": valid,
                "checked_at": now_ts,
                "expires_at": expires_at,
                "grace_until": grace_until,
                "reason": reason,
            }
            with self._lock:
                self._runtime["license"] = license_state
            self._persist()
            return license_state

        previous = self.status().get("license", {})
        grace_until = int(previous.get("grace_until", 0) or 0)
        in_grace = grace_until >= now_ts
        fallback_state = {
            "status": "grace" if in_grace else "invalid",
            "valid": False,
            "checked_at": now_ts,
            "expires_at": int(previous.get("expires_at", 0) or 0),
            "grace_until": grace_until,
            "reason": f"license_check_failed:{status}",
        }
        with self._lock:
            self._runtime["license"] = fallback_state
        self._persist()
        return fallback_state

    def _is_license_allowed(self, license_state: dict[str, Any]) -> bool:
        if bool(license_state.get("valid", False)):
            return True
        status = str(license_state.get("status", "invalid"))
        if status == "grace" and int(license_state.get("grace_until", 0) or 0) >= _now():
            return True
        return False

    def _fetch_remote_config(self, *, force: bool = False) -> dict[str, Any]:
        etag = "" if force else str(self.status().get("etag", "") or "")
        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag
        tenant_code = urllib.parse.quote(str(getattr(self.settings, "cms_tenant_code", "") or ""))
        edge_id = urllib.parse.quote(str(self.status().get("edge_id", "") or ""))
        status, body, response_headers = self._request(
            "GET",
            f"/v1/edge/config/effective?tenant_code={tenant_code}&edge_id={edge_id}",
            payload=None,
            include_auth=True,
            headers=headers,
        )
        if status == 304:
            return {"status": "not_modified"}
        if status < 200 or status >= 300:
            raise RuntimeError(f"cms_config_fetch_failed:{status}")

        contract_version = str(body.get("contract_version", "1"))
        if contract_version and not contract_version.startswith("1"):
            raise RuntimeError(f"cms_contract_version_unsupported:{contract_version}")

        runtime_patch = body.get("runtime_patch")
        if not isinstance(runtime_patch, dict):
            runtime_patch = body.get("config")
        if not isinstance(runtime_patch, dict):
            runtime_patch = body.get("payload")
        if not isinstance(runtime_patch, dict):
            runtime_patch = {}
        result = {
            "status": "updated",
            "runtime_patch": runtime_patch,
            "config_version": int(body.get("config_version", body.get("version", 0)) or 0),
            "etag": str(response_headers.get("etag") or body.get("etag") or ""),
            "canary": body.get("canary") if isinstance(body.get("canary"), dict) else {},
        }
        return result

    def _apply_remote_config(self, config_item: dict[str, Any]) -> dict[str, Any]:
        runtime_patch = config_item.get("runtime_patch", {})
        if not isinstance(runtime_patch, dict):
            raise RuntimeError("cms_config_invalid_patch")
        if not runtime_patch:
            return {"applied": False, "reason": "empty_patch"}

        canary = config_item.get("canary", {})
        use_canary = bool(canary.get("enabled", False))
        if use_canary:
            policy = CanaryPolicy(
                cameras=canary.get("cameras", []),
                duration_sec=int(canary.get("duration_sec", 300) or 300),
                max_skipped_fps_increase=float(canary.get("max_skipped_fps_increase", 2.0) or 2.0),
                min_process_fps_ratio=float(canary.get("min_process_fps_ratio", 0.7) or 0.7),
                max_inference_latency_increase_pct=float(
                    canary.get("max_inference_latency_increase_pct", 35.0) or 35.0
                ),
            )
            latest_stats = self.stats_provider()
            candidate_config, applied_patch, _ = self.runtime_store.start_canary(
                runtime_patch, policy, latest_stats, time.time()
            )
        else:
            candidate_config = self.runtime_store.apply_runtime_patch(runtime_patch)
            applied_patch = runtime_patch

        self.state_store.put_runtime_overlay(self.runtime_tenant, self.runtime_store.runtime_overlay)
        if self.on_runtime_patch_applied is not None:
            self.on_runtime_patch_applied(applied_patch, candidate_config)
        with self._lock:
            self._runtime["last_known_good"] = {
                "runtime_patch": runtime_patch,
                "config_version": int(config_item.get("config_version", 0) or 0),
                "etag": str(config_item.get("etag", "") or ""),
                "applied_at": _now(),
            }
        return {"applied": True}

    def _restore_last_known_good(self) -> None:
        lkg = self.status().get("last_known_good", {})
        patch = lkg.get("runtime_patch", {}) if isinstance(lkg, dict) else {}
        if not isinstance(patch, dict) or not patch:
            return
        try:
            self.runtime_store.apply_runtime_patch(patch)
            self.state_store.put_runtime_overlay(self.runtime_tenant, self.runtime_store.runtime_overlay)
            with self._lock:
                self._runtime["metrics"]["rollback_applied"] += 1
                self._append_audit(
                    {
                        "ts": _now(),
                        "event": "lkg_rollback_applied",
                        "config_version": lkg.get("config_version", 0),
                        "etag": lkg.get("etag", ""),
                    }
                )
            self._persist()
        except Exception:
            logger.exception("Failed to restore last_known_good CMS config")

    def _append_audit(self, item: dict[str, Any]) -> None:
        audit = self._runtime.setdefault("audit", [])
        if not isinstance(audit, list):
            audit = []
        audit.append(item)
        self._runtime["audit"] = audit[-500:]

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        include_auth: bool = True,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any], dict[str, str]]:
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)

        if include_auth:
            mode = str(getattr(self.settings, "cms_auth_mode", "token"))
            if mode == "token":
                token = str(getattr(self.settings, "cms_token", "") or "")
            else:
                token = str(self._session.get("access_token", "") or "")
            if token:
                request_headers["Authorization"] = f"Bearer {token}"

        url = f"{str(getattr(self.settings, 'cms_url', '')).rstrip('/')}{path}"
        timeout = float(getattr(self.settings, "cms_request_timeout_sec", 8.0) or 8.0)
        if self.transport:
            return self.transport(method, url, request_headers, payload, timeout)
        return self._urllib_request(method, url, request_headers, payload, timeout)

    def _urllib_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any] | None,
        timeout: float,
    ) -> tuple[int, dict[str, Any], dict[str, str]]:
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="ignore")
                body = json.loads(raw) if raw else {}
                if not isinstance(body, dict):
                    body = {}
                response_headers = {str(k).lower(): str(v) for k, v in dict(response.headers).items()}
                return int(getattr(response, "status", 200)), body, response_headers
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="ignore")
            body = {}
            if raw:
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        body = parsed
                except Exception:
                    body = {}
            response_headers = {str(k).lower(): str(v) for k, v in dict(exc.headers or {}).items()}
            return int(exc.code), body, response_headers
        except urllib.error.URLError as exc:
            raise RuntimeError("cms_unreachable") from exc

    def _persist(self) -> None:
        if hasattr(self.state_store, "put_cms_runtime"):
            self.state_store.put_cms_runtime(self.status())

    def _fingerprint(self) -> str:
        return f"{self.node_id}:{self.frigate_version}:{getattr(self.settings, 'cms_tenant_code', '')}"
