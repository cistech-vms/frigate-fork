import hashlib
import json
import time
from typing import Any


class IdempotencyStore:
    def __init__(self, ttl_sec: int = 3600) -> None:
        self.ttl_sec = max(60, int(ttl_sec))
        self._items: dict[str, dict[str, Any]] = {}

    def _now(self) -> int:
        return int(time.time())

    def _purge(self) -> None:
        now = self._now()
        keys = [k for k, v in self._items.items() if int(v.get("expire_at", 0)) <= now]
        for k in keys:
            self._items.pop(k, None)

    def build_key(self, tenant_id: str, request_key: str, payload: Any) -> str:
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]
        return f"{tenant_id}:{request_key}:{payload_hash}"

    def record_or_get(
        self, tenant_id: str, request_key: str, payload: Any
    ) -> tuple[bool, dict[str, Any]]:
        self._purge()
        key = self.build_key(tenant_id, request_key, payload)
        item = self._items.get(key)
        if item:
            return True, item
        created = {
            "tenant_id": tenant_id,
            "request_key": request_key,
            "recorded_at": self._now(),
            "expire_at": self._now() + self.ttl_sec,
            "deduplicated": False,
        }
        self._items[key] = created
        return False, created

    def snapshot(self, limit: int = 200) -> list[dict[str, Any]]:
        self._purge()
        return list(self._items.values())[-max(1, min(1000, int(limit))):]
