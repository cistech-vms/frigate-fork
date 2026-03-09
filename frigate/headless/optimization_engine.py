import statistics
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OptimizationEngine:
    state: dict[str, Any] = field(
        default_factory=lambda: {
            "baseline": {},
            "targets": {
                "inference_latency_p95_ms": 250.0,
                "queue_depth_max": 1500,
                "drop_rate_max_pct": 1.0,
                "event_delivery_latency_p95_ms": 800.0,
            },
            "ingest_decode": {},
            "inference_tuning": {},
            "tracking_regions": {},
            "event_rules": {},
            "queues": {
                "critical": 0,
                "normal": 0,
                "best_effort": 0,
                "drops": 0,
            },
            "delivery_efficiency": {
                "ttl_by_criticality": {
                    "critical": 86400,
                    "normal": 21600,
                    "best_effort": 3600,
                },
                "backlog": 0,
                "dlq": [],
            },
            "benchmarks": [],
            "playbook": {
                "symptoms": {
                    "high_latency": ["reduce detect fps", "reduce detect resolution"],
                    "growing_queue": ["raise backpressure", "drop best effort"],
                    "high_false_positive": ["increase confidence threshold", "apply exclusion masks"],
                    "event_loss": ["increase retry window", "inspect destination latency"],
                },
                "weekly_reports": [],
            },
        }
    )

    def collect_baseline(self, tier: str, profile: dict[str, Any]) -> dict[str, Any]:
        entry = {
            "tier": tier,
            "profile": profile,
            "captured_at": int(time.time()),
        }
        self.state["baseline"][tier] = entry
        return entry

    def set_targets(self, targets: dict[str, float]) -> dict[str, Any]:
        for k, v in targets.items():
            self.state["targets"][k] = float(v)
        self.state["targets"]["updated_at"] = int(time.time())
        return self.state["targets"]

    def configure_ingest_decode(self, tenant_id: str, config: dict[str, Any]) -> dict[str, Any]:
        self.state["ingest_decode"][tenant_id] = {
            **config,
            "updated_at": int(time.time()),
        }
        return self.state["ingest_decode"][tenant_id]

    def configure_inference(self, tenant_id: str, config: dict[str, Any]) -> dict[str, Any]:
        self.state["inference_tuning"][tenant_id] = {
            **config,
            "updated_at": int(time.time()),
        }
        return self.state["inference_tuning"][tenant_id]

    def configure_tracking_regions(self, tenant_id: str, config: dict[str, Any]) -> dict[str, Any]:
        self.state["tracking_regions"][tenant_id] = {
            **config,
            "updated_at": int(time.time()),
        }
        return self.state["tracking_regions"][tenant_id]

    def configure_event_rules(self, tenant_id: str, rules: dict[str, Any]) -> dict[str, Any]:
        self.state["event_rules"][tenant_id] = {
            **rules,
            "updated_at": int(time.time()),
        }
        return self.state["event_rules"][tenant_id]

    def enqueue(self, priority: str, amount: int = 1) -> dict[str, Any]:
        amount = max(1, int(amount))
        q = self.state["queues"]
        p = priority if priority in {"critical", "normal", "best_effort"} else "normal"
        q[p] += amount
        if q[p] > 4000 and p != "critical":
            q["drops"] += amount
            q[p] = max(0, q[p] - amount)
            return {"accepted": False, "reason": "backpressure_drop", "priority": p}
        return {"accepted": True, "priority": p, "depth": q[p]}

    def process_queue(self, amount: int = 200) -> dict[str, Any]:
        amount = max(1, int(amount))
        q = self.state["queues"]
        processed = 0
        for p in ("critical", "normal", "best_effort"):
            if processed >= amount:
                break
            take = min(q[p], amount - processed)
            q[p] -= take
            processed += take
        self.state["delivery_efficiency"]["backlog"] = q["critical"] + q["normal"] + q["best_effort"]
        return {"processed": processed, "queues": dict(q)}

    def configure_delivery_efficiency(self, config: dict[str, Any]) -> dict[str, Any]:
        self.state["delivery_efficiency"].update(config)
        self.state["delivery_efficiency"]["updated_at"] = int(time.time())
        return self.state["delivery_efficiency"]

    def record_benchmark(
        self,
        *,
        cameras: int,
        inference_p95_ms: float,
        event_delivery_p95_ms: float,
        drop_rate_pct: float,
        queue_depth: int,
        chaos_scenario: str | None = None,
    ) -> dict[str, Any]:
        item = {
            "cameras": int(cameras),
            "inference_p95_ms": float(inference_p95_ms),
            "event_delivery_p95_ms": float(event_delivery_p95_ms),
            "drop_rate_pct": float(drop_rate_pct),
            "queue_depth": int(queue_depth),
            "chaos_scenario": chaos_scenario,
            "ts": int(time.time()),
        }
        self.state["benchmarks"].append(item)
        self.state["benchmarks"] = self.state["benchmarks"][-400:]
        return item

    def benchmark_gate(self) -> dict[str, Any]:
        items = self.state["benchmarks"]
        if not items:
            return {"passed": False, "reason": "no_benchmarks"}
        latest = items[-20:]
        inf = max(i["inference_p95_ms"] for i in latest)
        evt = max(i["event_delivery_p95_ms"] for i in latest)
        drp = max(i["drop_rate_pct"] for i in latest)
        qd = max(i["queue_depth"] for i in latest)
        t = self.state["targets"]
        passed = (
            inf <= float(t["inference_latency_p95_ms"])
            and evt <= float(t["event_delivery_latency_p95_ms"])
            and drp <= float(t["drop_rate_max_pct"])
            and qd <= float(t["queue_depth_max"])
        )
        return {
            "passed": passed,
            "max_inference_p95_ms": inf,
            "max_event_delivery_p95_ms": evt,
            "max_drop_rate_pct": drp,
            "max_queue_depth": qd,
        }

    def weekly_report(self) -> dict[str, Any]:
        items = self.state["benchmarks"][-100:]
        if not items:
            report = {"generated_at": int(time.time()), "status": "no_data"}
            self.state["playbook"]["weekly_reports"].append(report)
            return report
        report = {
            "generated_at": int(time.time()),
            "avg_inference_p95_ms": round(
                statistics.mean([x["inference_p95_ms"] for x in items]), 2
            ),
            "avg_event_delivery_p95_ms": round(
                statistics.mean([x["event_delivery_p95_ms"] for x in items]), 2
            ),
            "avg_drop_rate_pct": round(statistics.mean([x["drop_rate_pct"] for x in items]), 3),
            "max_queue_depth": max(x["queue_depth"] for x in items),
            "gate": self.benchmark_gate(),
        }
        self.state["playbook"]["weekly_reports"].append(report)
        self.state["playbook"]["weekly_reports"] = self.state["playbook"]["weekly_reports"][-52:]
        return report

    def snapshot(self) -> dict[str, Any]:
        return self.state
