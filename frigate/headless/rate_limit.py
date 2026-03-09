import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Any

from frigate.const import CONFIG_DIR
from frigate.headless.redis_adapter import RedisAdapter

RATE_LIMIT_STATE_PATH = f"{CONFIG_DIR}/headless_rate_limit.json"


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    reason: str
    retry_after_sec: int
    key: str
    blocked_until: int


class DistributedRateLimiter:
    def __init__(
        self,
        *,
        limit_per_minute: int,
        state_path: str = RATE_LIMIT_STATE_PATH,
        block_base_sec: int = 30,
        block_max_sec: int = 900,
        fallback_limit_per_minute: int | None = None,
        redis_adapter: RedisAdapter | None = None,
    ) -> None:
        self.limit_per_minute = max(1, int(limit_per_minute))
        self.state_path = state_path
        self.block_base_sec = max(1, int(block_base_sec))
        self.block_max_sec = max(self.block_base_sec, int(block_max_sec))
        self.fallback_limit_per_minute = max(
            1, int(fallback_limit_per_minute or limit_per_minute)
        )
        self.redis_adapter = redis_adapter
        self._lock = threading.Lock()
        self._fallback_buckets: dict[str, tuple[int, int]] = {}

    def _default_state(self) -> dict[str, Any]:
        return {"version": 1, "keys": {}}

    def _load_state(self) -> dict[str, Any]:
        if not os.path.exists(self.state_path):
            return self._default_state()
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict) and isinstance(payload.get("keys"), dict):
                return payload
        except Exception:
            return self._default_state()
        return self._default_state()

    def _save_state(self, state: dict[str, Any]) -> None:
        base_dir = os.path.dirname(self.state_path) or "."
        os.makedirs(base_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=".headless_rate_limit_", dir=base_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, separators=(",", ":"), sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.state_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _allow_fallback(self, key: str) -> RateLimitDecision:
        now_minute = int(time.time() // 60)
        with self._lock:
            minute, count = self._fallback_buckets.get(key, (now_minute, 0))
            if minute != now_minute:
                minute, count = now_minute, 0
            count += 1
            self._fallback_buckets[key] = (minute, count)
            allowed = count <= self.fallback_limit_per_minute
            retry_after = max(1, (now_minute + 1) * 60 - int(time.time()))
            return RateLimitDecision(
                allowed=allowed,
                reason="ok_fallback" if allowed else "rate_limit_exceeded_fallback",
                retry_after_sec=0 if allowed else retry_after,
                key=key,
                blocked_until=0,
            )

    def allow(self, key: str, now_ts: float | None = None) -> RateLimitDecision:
        now_ts = now_ts or time.time()
        now_int = int(now_ts)
        now_minute = int(now_ts // 60)

        if self.redis_adapter is not None:
            decision = self._allow_redis(key, now_int, now_minute)
            if decision is not None:
                return decision

        try:
            with self._lock:
                state = self._load_state()
                keys = state.setdefault("keys", {})
                current = keys.get(key, {})
                blocked_until = int(current.get("blocked_until", 0) or 0)
                if blocked_until > now_int:
                    return RateLimitDecision(
                        allowed=False,
                        reason="temporarily_blocked",
                        retry_after_sec=max(1, blocked_until - now_int),
                        key=key,
                        blocked_until=blocked_until,
                    )

                minute = int(current.get("minute", now_minute))
                count = int(current.get("count", 0))
                violations = int(current.get("violations", 0))
                if minute != now_minute:
                    minute = now_minute
                    count = 0

                count += 1
                if count <= self.limit_per_minute:
                    keys[key] = {
                        "minute": minute,
                        "count": count,
                        "violations": violations,
                        "blocked_until": 0,
                    }
                    self._save_state(state)
                    return RateLimitDecision(
                        allowed=True,
                        reason="ok",
                        retry_after_sec=0,
                        key=key,
                        blocked_until=0,
                    )

                violations += 1
                penalty = min(self.block_max_sec, self.block_base_sec * (2 ** (violations - 1)))
                blocked_until = now_int + penalty
                keys[key] = {
                    "minute": minute,
                    "count": count,
                    "violations": violations,
                    "blocked_until": blocked_until,
                }
                self._save_state(state)
                return RateLimitDecision(
                    allowed=False,
                    reason="rate_limit_exceeded",
                    retry_after_sec=penalty,
                    key=key,
                    blocked_until=blocked_until,
                )
        except Exception:
            return self._allow_fallback(key)

    def _allow_redis(
        self, key: str, now_int: int, now_minute: int
    ) -> RateLimitDecision | None:
        if self.redis_adapter is None:
            return None
        try:
            block_key = f"frigate:rate:block:{key}"
            counter_key = f"frigate:rate:count:{now_minute}:{key}"
            v_key = f"frigate:rate:violations:{key}"

            blocked = self.redis_adapter.get_json(block_key)
            if blocked and int(blocked.get("blocked_until", 0)) > now_int:
                retry = max(1, int(blocked["blocked_until"]) - now_int)
                return RateLimitDecision(
                    allowed=False,
                    reason="temporarily_blocked",
                    retry_after_sec=retry,
                    key=key,
                    blocked_until=int(blocked["blocked_until"]),
                )

            count = self.redis_adapter.incr_with_ttl(counter_key, ttl_sec=70)
            if count <= self.limit_per_minute:
                return RateLimitDecision(
                    allowed=True,
                    reason="ok",
                    retry_after_sec=0,
                    key=key,
                    blocked_until=0,
                )

            violations = self.redis_adapter.incr_with_ttl(v_key, ttl_sec=3600)
            penalty = min(self.block_max_sec, self.block_base_sec * (2 ** (violations - 1)))
            blocked_until = now_int + penalty
            self.redis_adapter.set_json(
                block_key,
                {"blocked_until": blocked_until},
                ttl_sec=penalty,
            )
            return RateLimitDecision(
                allowed=False,
                reason="rate_limit_exceeded",
                retry_after_sec=penalty,
                key=key,
                blocked_until=blocked_until,
            )
        except Exception:
            return None
