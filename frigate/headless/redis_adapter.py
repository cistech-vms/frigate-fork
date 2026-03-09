import json
import os
from typing import Any


class RedisAdapter:
    def __init__(self, url: str) -> None:
        self.url = url
        self.enabled = False
        self._client = None
        try:
            import redis  # type: ignore

            self._client = redis.Redis.from_url(url, decode_responses=True)
            self._client.ping()
            self.enabled = True
        except Exception:
            self.enabled = False

    def incr_with_ttl(self, key: str, ttl_sec: int) -> int:
        if not self.enabled or self._client is None:
            raise RuntimeError("redis_unavailable")
        pipe = self._client.pipeline()
        pipe.incr(key, 1)
        pipe.expire(key, max(1, int(ttl_sec)))
        result = pipe.execute()
        return int(result[0])

    def set_json(self, key: str, value: dict[str, Any], ttl_sec: int) -> None:
        if not self.enabled or self._client is None:
            raise RuntimeError("redis_unavailable")
        self._client.setex(key, max(1, int(ttl_sec)), json.dumps(value, separators=(",", ":")))

    def get_json(self, key: str) -> dict[str, Any] | None:
        if not self.enabled or self._client is None:
            raise RuntimeError("redis_unavailable")
        raw = self._client.get(key)
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
        return None


def build_redis_adapter() -> RedisAdapter | None:
    enabled = os.getenv("FRIGATE_REDIS_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not enabled:
        return None
    url = os.getenv("FRIGATE_REDIS_URL", "redis://127.0.0.1:6379/0")
    adapter = RedisAdapter(url=url)
    if not adapter.enabled:
        return None
    return adapter
