import random
import threading
import time
from typing import Any

from frigate.headless.object_storage import ObjectStorageAdapter, encode_json_bytes
from frigate.headless.state_persistence import HeadlessStateStore


class StorageSyncManager:
    def __init__(
        self,
        *,
        state_store: HeadlessStateStore,
        object_storage: ObjectStorageAdapter,
        poll_interval_sec: float = 0.5,
        max_attempts: int = 5,
    ) -> None:
        self.state_store = state_store
        self.object_storage = object_storage
        self.poll_interval_sec = max(0.1, float(poll_interval_sec))
        self.max_attempts = max(1, int(max_attempts))
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="storage_sync_reconciler", daemon=True
        )
        persisted = self.state_store.load().get("storage_runtime", {})
        self._runtime: dict[str, Any] = {
            "configs": persisted.get("configs", {}),
            "sync": persisted.get(
                "sync",
                {
                    "backlog": 0,
                    "throughput": 0,
                    "failures": 0,
                    "last_success_ts": 0,
                    "dead_letters": [],
                },
            ),
        }
        self._queue: list[dict[str, Any]] = []

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def update_storage_config(self, tenant_id: str, config: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            current = self._runtime.setdefault("configs", {}).get(tenant_id, {})
            version = int(current.get("storage_config_version", 0)) + 1
            record = {
                "storage_config_version": version,
                "provider": config.get("provider", "local"),
                "bucket": config.get("bucket"),
                "region": config.get("region"),
                "endpoint": config.get("endpoint"),
                "prefix": config.get("prefix", "frigate"),
                "updated_at": int(time.time()),
            }
            self._runtime["configs"][tenant_id] = record
            self._persist_locked()
            return record

    def enqueue_replication(self, tenant_id: str, key: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._queue.append(
                {
                    "tenant_id": tenant_id,
                    "key": key,
                    "payload": payload,
                    "attempts": 0,
                    "next_attempt_ts": time.time(),
                    "created_at": int(time.time()),
                }
            )
            self._runtime.setdefault("sync", {})["backlog"] = len(self._queue)
            self._persist_locked()

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._runtime.setdefault("sync", {})["backlog"] = len(self._queue)
            return {
                "backlog": self._runtime["sync"].get("backlog", 0),
                "throughput": self._runtime["sync"].get("throughput", 0),
                "failures": self._runtime["sync"].get("failures", 0),
                "last_success_ts": self._runtime["sync"].get("last_success_ts", 0),
                "dead_letters": self._runtime["sync"].get("dead_letters", []),
                "configs": self._runtime.get("configs", {}),
            }

    def _run(self) -> None:
        while not self._stop.wait(self.poll_interval_sec):
            self.process_due()

    def process_due(self) -> None:
        now = time.time()
        due: list[dict[str, Any]] = []
        with self._lock:
            keep: list[dict[str, Any]] = []
            for item in self._queue:
                if float(item.get("next_attempt_ts", 0.0)) <= now:
                    due.append(item)
                else:
                    keep.append(item)
            self._queue = keep

        for item in due:
            self._replicate(item)

    def _replicate(self, item: dict[str, Any]) -> None:
        tenant = item["tenant_id"]
        key = item["key"]
        try:
            object_key = f"{tenant}/{key}".lstrip("/")
            self.object_storage.put_object(
                object_key,
                encode_json_bytes(item["payload"]),
                content_type="application/json",
            )
            with self._lock:
                self._runtime["sync"]["throughput"] = int(self._runtime["sync"].get("throughput", 0)) + 1
                self._runtime["sync"]["last_success_ts"] = int(time.time())
                self._runtime["sync"]["backlog"] = len(self._queue)
                self._persist_locked()
            return
        except Exception:
            pass

        item["attempts"] = int(item.get("attempts", 0)) + 1
        if item["attempts"] >= self.max_attempts:
            with self._lock:
                dead = self._runtime["sync"].setdefault("dead_letters", [])
                dead.append(
                    {
                        "tenant_id": tenant,
                        "key": key,
                        "attempts": item["attempts"],
                        "created_at": item["created_at"],
                        "dead_at": int(time.time()),
                    }
                )
                self._runtime["sync"]["dead_letters"] = dead[-200:]
                self._runtime["sync"]["failures"] = int(self._runtime["sync"].get("failures", 0)) + 1
                self._runtime["sync"]["backlog"] = len(self._queue)
                self._persist_locked()
            return

        backoff = min(60.0, 2.0 ** (item["attempts"] - 1))
        item["next_attempt_ts"] = time.time() + backoff + random.random()
        with self._lock:
            self._queue.append(item)
            self._runtime["sync"]["backlog"] = len(self._queue)
            self._persist_locked()

    def _persist_locked(self) -> None:
        self.state_store.put_storage_runtime(self._runtime)
