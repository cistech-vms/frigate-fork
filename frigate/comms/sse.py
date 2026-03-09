"""In-process event stream communicator used by headless SSE clients."""

import queue
import threading
from typing import Any, Callable

from frigate.comms.base_communicator import Communicator


class SseEventClient(Communicator):
    def __init__(self) -> None:
        self._receiver: Callable | None = None
        self._subscribers: list[queue.Queue] = []
        self._lock = threading.Lock()

    def subscribe(self, receiver: Callable) -> None:
        self._receiver = receiver

    def register_stream(self, maxsize: int = 500) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=maxsize)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unregister_stream(self, q: queue.Queue) -> None:
        with self._lock:
            self._subscribers = [item for item in self._subscribers if item is not q]

    def stream_health(self) -> dict[str, float | int]:
        with self._lock:
            subscribers = list(self._subscribers)

        if not subscribers:
            return {"subscribers": 0, "max_fill_ratio": 0.0}

        max_ratio = 0.0
        for item in subscribers:
            max_size = float(item.maxsize or 0)
            if max_size <= 0:
                continue
            ratio = min(1.0, float(item.qsize()) / max_size)
            if ratio > max_ratio:
                max_ratio = ratio

        return {"subscribers": len(subscribers), "max_fill_ratio": round(max_ratio, 4)}

    def publish(self, topic: str, payload: Any, retain: bool = False) -> None:
        del retain
        event = {"topic": topic, "payload": payload}
        with self._lock:
            subscribers = list(self._subscribers)

        for q in subscribers:
            try:
                q.put_nowait(event)
            except queue.Full:
                # Drop oldest event to preserve backpressure safety.
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    continue

    def stop(self) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
            self._subscribers = []

        for q in subscribers:
            try:
                q.put_nowait(None)
            except Exception:
                pass
