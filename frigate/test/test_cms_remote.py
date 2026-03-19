import copy
import unittest
from types import SimpleNamespace

from frigate.headless.cms_remote import CmsRemoteManager


class FakeStateStore:
    def __init__(self):
        self._cms_runtime = {}
        self._runtime_overlays = {}

    def cms_runtime(self):
        return copy.deepcopy(self._cms_runtime)

    def put_cms_runtime(self, runtime):
        self._cms_runtime = copy.deepcopy(runtime)
        return self._cms_runtime

    def put_runtime_overlay(self, tenant_id, runtime_overlay):
        self._runtime_overlays[tenant_id] = copy.deepcopy(runtime_overlay)
        return self._runtime_overlays


class FakeRuntimeStore:
    def __init__(self):
        self.runtime_overlay = {}
        self.canary_started = False

    def apply_runtime_patch(self, runtime_patch):
        if runtime_patch.get("invalid", False):
            raise ValueError("invalid_patch")
        for key, value in runtime_patch.items():
            self.runtime_overlay[key] = value
        return runtime_patch

    def start_canary(self, runtime_patch, policy, latest_stats, now_ts):
        del policy, latest_stats, now_ts
        self.canary_started = True
        self.apply_runtime_patch(runtime_patch)
        return runtime_patch, runtime_patch, {"status": "running"}


class TestCmsRemoteManager(unittest.TestCase):
    def test_token_auth_sync_and_apply(self):
        settings = SimpleNamespace(
            cms_enabled=True,
            cms_url="http://cms.local",
            cms_auth_mode="token",
            cms_token="abc",
            cms_username=None,
            cms_password=None,
            cms_tenant_code="tenant-a",
            cms_sync_interval_sec=60,
            cms_request_timeout_sec=3.0,
            cms_license_grace_sec=300,
        )
        state_store = FakeStateStore()
        runtime_store = FakeRuntimeStore()
        applied = []

        def transport(method, url, headers, payload, timeout):
            del headers, timeout
            if method == "POST" and url.endswith("/v1/edge/enroll"):
                self.assertEqual(payload["tenant_code"], "tenant-a")
                return 200, {"edge_id": "edge-1"}, {}
            if method == "POST" and url.endswith("/v1/edge/license/validate"):
                return 200, {"valid": True, "expires_at": 2000000000}, {}
            if method == "GET" and "/v1/edge/config/effective" in url:
                return (
                    200,
                    {
                        "runtime_patch": {"mqtt": {"enabled": False}},
                        "config_version": 3,
                        "etag": "cfg-3",
                    },
                    {},
                )
            raise AssertionError(f"unexpected call: {method} {url}")

        manager = CmsRemoteManager(
            settings=settings,
            state_store=state_store,
            runtime_store=runtime_store,
            stats_provider=lambda: {"cameras": {}},
            runtime_tenant="tenant-a",
            node_id="node-1",
            frigate_version="1.0",
            transport=transport,
            on_runtime_patch_applied=lambda patch, candidate: applied.append(
                (copy.deepcopy(patch), copy.deepcopy(candidate))
            ),
        )

        snapshot = manager.sync_once(force=True)

        self.assertTrue(snapshot["connected"])
        self.assertEqual(snapshot["edge_id"], "edge-1")
        self.assertEqual(snapshot["config_version"], 3)
        self.assertEqual(runtime_store.runtime_overlay["mqtt"]["enabled"], False)
        self.assertEqual(applied[0][0], {"mqtt": {"enabled": False}})

    def test_password_auth_flow(self):
        settings = SimpleNamespace(
            cms_enabled=True,
            cms_url="http://cms.local",
            cms_auth_mode="password",
            cms_token=None,
            cms_username="user",
            cms_password="pass",
            cms_tenant_code="tenant-a",
            cms_sync_interval_sec=60,
            cms_request_timeout_sec=3.0,
            cms_license_grace_sec=300,
        )
        state_store = FakeStateStore()
        runtime_store = FakeRuntimeStore()

        def transport(method, url, headers, payload, timeout):
            del headers, timeout
            if method == "POST" and url.endswith("/v1/edge/auth/login"):
                self.assertEqual(payload["username"], "user")
                return 200, {"access_token": "tok", "refresh_token": "ref", "expires_in": 1200}, {}
            if method == "POST" and url.endswith("/v1/edge/enroll"):
                return 200, {"edge_id": "edge-2"}, {}
            if method == "POST" and url.endswith("/v1/edge/license/validate"):
                return 200, {"valid": True}, {}
            if method == "GET" and "/v1/edge/config/effective" in url:
                return 200, {"runtime_patch": {"record": {"enabled": False}}}, {}
            raise AssertionError(f"unexpected call: {method} {url}")

        manager = CmsRemoteManager(
            settings=settings,
            state_store=state_store,
            runtime_store=runtime_store,
            stats_provider=lambda: {"cameras": {}},
            runtime_tenant="tenant-a",
            node_id="node-1",
            frigate_version="1.0",
            transport=transport,
        )

        snapshot = manager.sync_once(force=True)

        self.assertEqual(snapshot["auth"]["status"], "active")
        self.assertGreaterEqual(snapshot["metrics"]["auth_success"], 1)
        self.assertEqual(runtime_store.runtime_overlay["record"]["enabled"], False)

    def test_not_modified_config(self):
        settings = SimpleNamespace(
            cms_enabled=True,
            cms_url="http://cms.local",
            cms_auth_mode="token",
            cms_token="abc",
            cms_username=None,
            cms_password=None,
            cms_tenant_code="tenant-a",
            cms_sync_interval_sec=60,
            cms_request_timeout_sec=3.0,
            cms_license_grace_sec=300,
        )
        state_store = FakeStateStore()
        state_store._cms_runtime = {"edge_id": "edge-1", "etag": "etag-1"}
        runtime_store = FakeRuntimeStore()

        def transport(method, url, headers, payload, timeout):
            del payload, timeout
            if method == "POST" and url.endswith("/v1/edge/license/validate"):
                return 200, {"valid": True}, {}
            if method == "GET" and "/v1/edge/config/effective" in url:
                self.assertEqual(headers.get("If-None-Match"), "etag-1")
                return 304, {}, {}
            raise AssertionError(f"unexpected call: {method} {url}")

        manager = CmsRemoteManager(
            settings=settings,
            state_store=state_store,
            runtime_store=runtime_store,
            stats_provider=lambda: {"cameras": {}},
            runtime_tenant="tenant-a",
            node_id="node-1",
            frigate_version="1.0",
            transport=transport,
        )

        snapshot = manager.sync_once(force=False)

        self.assertTrue(snapshot["connected"])
        self.assertGreaterEqual(snapshot["metrics"]["config_unchanged"], 1)

    def test_enrich_readiness_blocks_on_invalid_license(self):
        settings = SimpleNamespace(
            cms_enabled=True,
            cms_url="http://cms.local",
            cms_auth_mode="token",
            cms_token="abc",
            cms_username=None,
            cms_password=None,
            cms_tenant_code="tenant-a",
            cms_sync_interval_sec=60,
            cms_request_timeout_sec=3.0,
            cms_license_grace_sec=0,
        )
        state_store = FakeStateStore()
        runtime_store = FakeRuntimeStore()

        manager = CmsRemoteManager(
            settings=settings,
            state_store=state_store,
            runtime_store=runtime_store,
            stats_provider=lambda: {"cameras": {}},
            runtime_tenant="tenant-a",
            node_id="node-1",
            frigate_version="1.0",
            transport=lambda *args, **kwargs: (500, {}, {}),
        )

        manager._runtime["connected"] = False
        manager._runtime["last_sync_ts"] = 0
        manager._runtime["license"] = {
            "status": "invalid",
            "valid": False,
            "checked_at": 0,
            "expires_at": 0,
            "grace_until": 0,
            "reason": "invalid",
        }

        readiness = {
            "ready": True,
            "mode": "normal",
            "write_critical_allowed": True,
            "reasons": [],
            "warnings": [],
            "checks": {},
        }

        enriched = manager.enrich_readiness(readiness)

        self.assertFalse(enriched["ready"])
        self.assertFalse(enriched["write_critical_allowed"])
        self.assertIn("cms_license_invalid", enriched["reasons"])

    def test_restore_last_known_good_on_failed_apply(self):
        settings = SimpleNamespace(
            cms_enabled=True,
            cms_url="http://cms.local",
            cms_auth_mode="token",
            cms_token="abc",
            cms_username=None,
            cms_password=None,
            cms_tenant_code="tenant-a",
            cms_sync_interval_sec=60,
            cms_request_timeout_sec=3.0,
            cms_license_grace_sec=300,
        )
        state_store = FakeStateStore()
        runtime_store = FakeRuntimeStore()
        calls = {"n": 0}

        def transport(method, url, headers, payload, timeout):
            del headers, payload, timeout
            if method == "POST" and url.endswith("/v1/edge/enroll"):
                return 200, {"edge_id": "edge-1"}, {}
            if method == "POST" and url.endswith("/v1/edge/license/validate"):
                return 200, {"valid": True}, {}
            if method == "GET" and "/v1/edge/config/effective" in url:
                calls["n"] += 1
                if calls["n"] == 1:
                    return 200, {"runtime_patch": {"mqtt": {"enabled": False}}, "config_version": 1}, {}
                return 200, {"runtime_patch": {"invalid": True}, "config_version": 2}, {}
            raise AssertionError(f"unexpected call: {method} {url}")

        manager = CmsRemoteManager(
            settings=settings,
            state_store=state_store,
            runtime_store=runtime_store,
            stats_provider=lambda: {"cameras": {}},
            runtime_tenant="tenant-a",
            node_id="node-1",
            frigate_version="1.0",
            transport=transport,
        )

        first = manager.sync_once(force=True)
        self.assertTrue(first["connected"])
        self.assertEqual(runtime_store.runtime_overlay["mqtt"]["enabled"], False)

        second = manager.sync_once(force=True)
        self.assertFalse(second["connected"])
        self.assertEqual(runtime_store.runtime_overlay["mqtt"]["enabled"], False)
        self.assertGreaterEqual(second["metrics"]["rollback_applied"], 1)


if __name__ == "__main__":
    unittest.main()
