import json
import random
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from frigate.comms.sse import SseEventClient
from frigate.headless.state_persistence import HeadlessStateStore


class ReliableEventDelivery:
    def __init__(
        self,
        *,
        sse_client: SseEventClient,
        state_store: HeadlessStateStore,
        storage_sync_manager: Any | None = None,
        webhook_url: str | None = None,
        max_attempts: int = 5,
        backoff_base_sec: float = 1.0,
        backoff_max_sec: float = 30.0,
        jitter_ratio: float = 0.2,
        poll_interval_sec: float = 0.5,
    ) -> None:
        self.sse_client = sse_client
        self.state_store = state_store
        self.webhook_url = (webhook_url or "").strip() or None
        self.storage_sync_manager = storage_sync_manager
        self.max_attempts = max(1, int(max_attempts))
        self.backoff_base_sec = max(0.1, float(backoff_base_sec))
        self.backoff_max_sec = max(self.backoff_base_sec, float(backoff_max_sec))
        self.jitter_ratio = max(0.0, float(jitter_ratio))
        self.poll_interval_sec = max(0.1, float(poll_interval_sec))
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="reliable_event_delivery", daemon=True
        )
        self._pending: list[dict[str, Any]] = []
        self._known_keys: set[str] = set()
        persisted = self.state_store.load().get("event_delivery_status", {})
        self._status: dict[str, Any] = {
            "channels": persisted.get("channels", {}),
            "dead_letters": persisted.get("dead_letters", []),
            "last_updated": int(time.time()),
        }

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def emit(self, topic: str, payload: Any, event_id: str | None = None) -> str:
        event_id = event_id or str(uuid.uuid4())
        created_ts = time.time()
        jobs: list[dict[str, Any]] = []
        jobs.append(
            {
                "delivery_id": str(uuid.uuid4()),
                "event_id": event_id,
                "topic": topic,
                "payload": payload,
                "channel": "sse",
                "attempts": 0,
                "created_at": created_ts,
                "next_attempt_ts": created_ts,
                "last_error": "",
            }
        )
        if self.webhook_url:
            jobs.append(
                {
                    "delivery_id": str(uuid.uuid4()),
                    "event_id": event_id,
                    "topic": topic,
                    "payload": payload,
                    "channel": "webhook",
                    "attempts": 0,
                    "created_at": created_ts,
                    "next_attempt_ts": created_ts,
                    "last_error": "",
                }
            )

        with self._lock:
            for job in jobs:
                key = f"{job['channel']}:{job['event_id']}:{job['topic']}"
                if key in self._known_keys:
                    continue
                self._known_keys.add(key)
                self._pending.append(job)
            self._persist_status_locked()
        return event_id

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            pending = len(self._pending)
            by_channel: dict[str, int] = {}
            for item in self._pending:
                by_channel[item["channel"]] = by_channel.get(item["channel"], 0) + 1
            status = {
                "pending_total": pending,
                "pending_by_channel": by_channel,
                "channels": self._status.get("channels", {}),
                "dead_letters": self._status.get("dead_letters", []),
                "last_updated": self._status.get("last_updated", int(time.time())),
            }
            return status

    def _run(self) -> None:
        while not self._stop_event.wait(self.poll_interval_sec):
            self.process_due()

    def process_due(self) -> None:
        now_ts = time.time()
        due: list[dict[str, Any]] = []
        with self._lock:
            keep: list[dict[str, Any]] = []
            for item in self._pending:
                if float(item.get("next_attempt_ts", 0.0)) <= now_ts:
                    due.append(item)
                else:
                    keep.append(item)
            self._pending = keep

        for item in due:
            self._deliver(item)

    def _channel_stats_locked(self, channel: str) -> dict[str, Any]:
        channels = self._status.setdefault("channels", {})
        return channels.setdefault(
            channel,
            {
                "success": 0,
                "failed": 0,
                "retried": 0,
                "dead_letter": 0,
                "last_error": "",
                "last_latency_ms": 0.0,
            },
        )

    def _persist_status_locked(self) -> None:
        self._status["last_updated"] = int(time.time())
        self.state_store.put_event_delivery_status(self._status)

    def _deliver(self, item: dict[str, Any]) -> None:
        started = time.time()
        channel = str(item["channel"])
        ok = False
        error_msg = ""
        try:
            if channel == "sse":
                self.sse_client.publish(item["topic"], item["payload"], retain=False)
                ok = True
            elif channel == "webhook":
                self._deliver_webhook(item)
                ok = True
            else:
                error_msg = f"unsupported_channel:{channel}"
        except Exception as exc:
            error_msg = str(exc)

        latency_ms = round((time.time() - started) * 1000, 2)
        with self._lock:
            stats = self._channel_stats_locked(channel)
            stats["last_latency_ms"] = latency_ms
            if ok:
                stats["success"] += 1
                self._persist_status_locked()
                return

            item["attempts"] = int(item.get("attempts", 0)) + 1
            item["last_error"] = error_msg
            stats["failed"] += 1
            stats["last_error"] = error_msg

            if item["attempts"] >= self.max_attempts:
                stats["dead_letter"] += 1
                dead = {
                    "delivery_id": item["delivery_id"],
                    "event_id": item["event_id"],
                    "topic": item["topic"],
                    "channel": channel,
                    "attempts": item["attempts"],
                    "last_error": error_msg,
                    "created_at": item["created_at"],
                    "dead_at": int(time.time()),
                }
                dead_letters: list[dict[str, Any]] = self._status.setdefault(
                    "dead_letters", []
                )
                dead_letters.append(dead)
                self._status["dead_letters"] = dead_letters[-200:]
                if self.storage_sync_manager is not None:
                    self.storage_sync_manager.enqueue_replication(
                        tenant_id="default",
                        key=f"dead-letter/{dead['delivery_id']}.json",
                        payload=dead,
                    )
                self._persist_status_locked()
                return

            backoff = min(
                self.backoff_max_sec,
                self.backoff_base_sec * (2 ** max(0, item["attempts"] - 1)),
            )
            jitter = backoff * self.jitter_ratio * random.random()
            item["next_attempt_ts"] = time.time() + backoff + jitter
            stats["retried"] += 1
            self._pending.append(item)
            self._persist_status_locked()

    def _deliver_webhook(self, item: dict[str, Any]) -> None:
        if not self.webhook_url:
            raise RuntimeError("webhook_not_configured")

        payload = {
            "topic": item["topic"],
            "payload": item["payload"],
            "event_id": item["event_id"],
            "delivery_id": item["delivery_id"],
            "attempt": int(item.get("attempts", 0)) + 1,
            "sent_at": int(time.time()),
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                status = int(getattr(response, "status", 200))
                if status < 200 or status >= 300:
                    raise RuntimeError(f"webhook_status_{status}")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"webhook_status_{exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("webhook_unreachable") from exc
