import asyncio
import os
import time
import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from frigate.headless.rate_limit import DistributedRateLimiter
from frigate.headless.security import Principal, require_role, resolve_tenant
from frigate.headless.settings import HeadlessSettings, get_headless_settings


def _build_request(
    *,
    auth_mode: str,
    headers: dict[str, str] | None = None,
    fixed_tenant_id: str | None = None,
    principal: Principal | None = None,
):
    settings = HeadlessSettings(
        enabled=True,
        auth_mode=auth_mode,
        hmac_max_skew_sec=300,
        rate_limit_per_minute=1000,
        tenant_id=fixed_tenant_id,
        cors_allowlist=[],
        metrics_enabled=True,
        readiness_warmup_sec=20,
        readiness_min_process_fps=0.1,
        readiness_max_skipped_process_ratio=2.0,
        readiness_max_sse_fill_ratio=0.95,
        rate_limit_block_base_sec=30,
        rate_limit_block_max_sec=900,
    )
    state = SimpleNamespace(
        headless_settings=settings,
        headless_rate_limiter=DistributedRateLimiter(
            limit_per_minute=1000,
            state_path="/tmp/headless_rate_limit_test.json",
        ),
    )
    request_state = SimpleNamespace(raw_body=b"{}")
    if principal is not None:
        request_state.principal = principal
    app = SimpleNamespace(state=state)
    return SimpleNamespace(
        app=app,
        client=SimpleNamespace(host="127.0.0.1"),
        headers=headers or {},
        state=request_state,
    )


class TestSecurityHardening(unittest.TestCase):
    def setUp(self):
        self.original_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_get_headless_settings_rejects_invalid_auth_mode(self):
        os.environ["FRIGATE_API_AUTH_MODE"] = "none"
        with self.assertRaises(ValueError):
            get_headless_settings()

    def test_require_role_invalid_auth_mode_is_fail_closed(self):
        checker = require_role("reader")
        request = _build_request(auth_mode="invalid")
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(checker(request))
        self.assertEqual(ctx.exception.status_code, 503)

    def test_hmac_auth_without_keys_is_denied(self):
        checker = require_role("reader")
        request = _build_request(
            auth_mode="hmac",
            headers={
                "x-key-id": "key-1",
                "x-signature": "sig",
                "x-timestamp": str(int(time.time())),
            },
        )
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(checker(request))
        self.assertEqual(ctx.exception.status_code, 503)

    def test_jwt_auth_without_secret_is_denied(self):
        checker = require_role("reader")
        request = _build_request(
            auth_mode="jwt",
            headers={"authorization": "Bearer token"},
        )
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(checker(request))
        self.assertEqual(ctx.exception.status_code, 503)

    def test_resolve_tenant_requires_explicit_tenant_in_multi_tenant_mode(self):
        request = _build_request(auth_mode="hmac")
        with self.assertRaises(HTTPException) as ctx:
            resolve_tenant(request)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_resolve_tenant_rejects_principal_tenant_mismatch(self):
        request = _build_request(
            auth_mode="hmac",
            headers={"x-tenant-id": "tenant-b"},
            principal=Principal(subject="key", role="admin", tenant_id="tenant-a"),
        )
        with self.assertRaises(HTTPException) as ctx:
            resolve_tenant(request)
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
