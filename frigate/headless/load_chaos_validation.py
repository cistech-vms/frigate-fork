import statistics
import time
from typing import Any


class LoadChaosValidator:
    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []

    def record(
        self,
        *,
        profile: str,
        latency_ms: float,
        event_loss_pct: float,
        backlog: int,
        recovery_sec: int,
    ) -> dict[str, Any]:
        item = {
            "profile": profile,
            "latency_ms": float(latency_ms),
            "event_loss_pct": float(event_loss_pct),
            "backlog": int(backlog),
            "recovery_sec": int(recovery_sec),
            "ts": int(time.time()),
        }
        self.results.append(item)
        self.results = self.results[-500:]
        return item

    def summary(self) -> dict[str, Any]:
        if not self.results:
            return {"count": 0, "gate_passed": False, "reason": "no_results"}
        latencies = [r["latency_ms"] for r in self.results]
        losses = [r["event_loss_pct"] for r in self.results]
        backlogs = [r["backlog"] for r in self.results]
        recoveries = [r["recovery_sec"] for r in self.results]
        summary = {
            "count": len(self.results),
            "latency_p95_ms": round(statistics.quantiles(latencies, n=20)[18], 2)
            if len(latencies) >= 20
            else round(max(latencies), 2),
            "max_event_loss_pct": round(max(losses), 3),
            "max_backlog": max(backlogs),
            "max_recovery_sec": max(recoveries),
        }
        summary["gate_passed"] = (
            summary["latency_p95_ms"] <= 3000
            and summary["max_event_loss_pct"] <= 1.0
            and summary["max_backlog"] <= 5000
            and summary["max_recovery_sec"] <= 300
        )
        return summary
