import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any


def _stable_etag(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class HorizontalScalingManager:
    node_id: str = "node-1"
    state: dict[str, Any] = field(
        default_factory=lambda: {
            "plans": {},
            "heartbeats": {},
            "shards": {},
            "event_pipeline": {
                "priority_queues": {"high": 0, "normal": 0, "low": 0},
                "dlq": [],
                "drops": 0,
                "throughput": 0,
                "errors": 0,
            },
            "storage": {
                "hot_state_backend": "local",
                "historical_backend": "local",
                "retention_by_tenant": {},
            },
            "rollout": {
                "active": {},
                "history": [],
            },
        }
    )

    def apply_plan(
        self,
        *,
        tenant_id: str,
        config_version: int,
        assigned_cameras: list[str],
        request_id: str | None = None,
        if_match: str | None = None,
    ) -> dict[str, Any]:
        if config_version < 1:
            raise ValueError("invalid_config_version")
        key = tenant_id
        current = self.state["plans"].get(key, {})
        if if_match and current.get("etag") and if_match != current.get("etag"):
            raise ValueError("etag_mismatch")

        desired = {
            "tenant_id": tenant_id,
            "node_id": self.node_id,
            "desired_version": config_version,
            "applied_version": config_version,
            "assigned_cameras": sorted(set(assigned_cameras)),
            "request_id": request_id or f"req-{int(time.time())}",
            "updated_at": int(time.time()),
        }
        desired["drift"] = int(desired["desired_version"]) - int(desired["applied_version"])
        desired["etag"] = _stable_etag(desired)
        self.state["plans"][key] = desired

        self._rebuild_shards_for_tenant(tenant_id)
        return desired

    def reconcile(self, tenant_id: str) -> dict[str, Any]:
        current = self.state["plans"].get(tenant_id)
        if not current:
            return {"tenant_id": tenant_id, "status": "missing"}
        current["drift"] = int(current["desired_version"]) - int(current["applied_version"])
        return {
            "tenant_id": tenant_id,
            "desired_version": current["desired_version"],
            "applied_version": current["applied_version"],
            "drift": current["drift"],
            "etag": current["etag"],
            "assigned_cameras": current["assigned_cameras"],
        }

    def heartbeat(
        self,
        *,
        tenant_id: str,
        fps: float,
        queue_depth: int,
        inference_latency_ms: float,
    ) -> dict[str, Any]:
        hb = {
            "tenant_id": tenant_id,
            "node_id": self.node_id,
            "fps": float(fps),
            "queue_depth": int(queue_depth),
            "inference_latency_ms": float(inference_latency_ms),
            "ts": int(time.time()),
        }
        self.state["heartbeats"][tenant_id] = hb
        return hb

    def _rebuild_shards_for_tenant(self, tenant_id: str) -> None:
        plan = self.state["plans"].get(tenant_id, {})
        cameras = plan.get("assigned_cameras", [])
        shards = {}
        for camera in cameras:
            shard_id = self._shard_id(tenant_id, camera)
            shards[shard_id] = {
                "tenant_id": tenant_id,
                "camera_id": camera,
                "max_queue": 2000,
                "max_fps": 30,
                "drop_policy": "drop_low_priority",
                "queue_depth": 0,
            }
        self.state["shards"].update(shards)

    def _shard_id(self, tenant_id: str, camera_id: str) -> str:
        digest = hashlib.sha1(f"{tenant_id}:{camera_id}".encode("utf-8")).hexdigest()[:8]
        return f"shard-{digest}"

    def rebalance(self, tenant_id: str, max_cameras_per_node: int = 32) -> dict[str, Any]:
        plan = self.state["plans"].get(tenant_id)
        if not plan:
            return {"status": "missing", "tenant_id": tenant_id}
        cameras = list(plan.get("assigned_cameras", []))
        overflow = max(0, len(cameras) - max_cameras_per_node)
        moved = cameras[-overflow:] if overflow > 0 else []
        retained = cameras[: len(cameras) - overflow] if overflow > 0 else cameras
        plan["assigned_cameras"] = retained
        plan["updated_at"] = int(time.time())
        plan["etag"] = _stable_etag(plan)
        self._rebuild_shards_for_tenant(tenant_id)
        return {
            "tenant_id": tenant_id,
            "status": "rebalanced",
            "retained": retained,
            "moved_out": moved,
            "hysteresis_applied": True,
        }

    def configure_storage_strategy(
        self,
        *,
        hot_state_backend: str,
        historical_backend: str,
        tenant_retention: dict[str, int],
    ) -> dict[str, Any]:
        self.state["storage"] = {
            "hot_state_backend": hot_state_backend,
            "historical_backend": historical_backend,
            "retention_by_tenant": tenant_retention,
            "updated_at": int(time.time()),
        }
        return self.state["storage"]

    def publish_event(
        self, *, tenant_id: str, priority: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        pipeline = self.state["event_pipeline"]
        queues = pipeline["priority_queues"]
        priority = priority if priority in queues else "normal"
        queues[priority] += 1
        if queues[priority] > 5000:
            pipeline["drops"] += 1
            pipeline["dlq"].append(
                {
                    "tenant_id": tenant_id,
                    "priority": priority,
                    "reason": "backpressure_drop",
                    "ts": int(time.time()),
                    "payload_hint": list(payload.keys())[:5],
                }
            )
            pipeline["dlq"] = pipeline["dlq"][-300:]
            return {"accepted": False, "reason": "backpressure_drop"}
        pipeline["throughput"] += 1
        return {"accepted": True, "queue_depth": queues[priority], "priority": priority}

    def process_event_tick(self, max_batch: int = 200) -> dict[str, Any]:
        pipeline = self.state["event_pipeline"]
        queues = pipeline["priority_queues"]
        processed = 0
        for priority in ("high", "normal", "low"):
            if processed >= max_batch:
                break
            available = queues[priority]
            take = min(available, max_batch - processed)
            queues[priority] -= take
            processed += take
        return {"processed": processed, "queues": dict(queues)}

    def shard_metrics(self) -> dict[str, Any]:
        total_shards = len(self.state["shards"])
        queue_depth = sum(int(v.get("queue_depth", 0)) for v in self.state["shards"].values())
        hb = self.state.get("heartbeats", {})
        avg_latency = 0.0
        if hb:
            avg_latency = sum(float(x.get("inference_latency_ms", 0.0)) for x in hb.values()) / len(hb)
        return {
            "total_shards": total_shards,
            "queue_depth": queue_depth,
            "avg_inference_latency_ms": round(avg_latency, 2),
            "drop_rate": self.state["event_pipeline"]["drops"],
        }

    def slo_snapshot(self) -> dict[str, Any]:
        metrics = self.shard_metrics()
        queues = self.state["event_pipeline"]["priority_queues"]
        total_queue = int(queues["high"] + queues["normal"] + queues["low"])
        return {
            "metrics": metrics,
            "slo": {
                "latency_ok": metrics["avg_inference_latency_ms"] <= 250.0,
                "queue_ok": total_queue <= 3000,
                "drop_ok": int(self.state["event_pipeline"]["drops"]) <= 200,
            },
            "queue_total": total_queue,
        }

    def start_canary(self, tenant_id: str, target_version: int, cameras: list[str]) -> dict[str, Any]:
        item = {
            "tenant_id": tenant_id,
            "target_version": target_version,
            "cameras": cameras,
            "started_at": int(time.time()),
            "status": "running",
        }
        self.state["rollout"]["active"][tenant_id] = item
        return item

    def finalize_canary(self, tenant_id: str, promote: bool) -> dict[str, Any]:
        current = self.state["rollout"]["active"].get(tenant_id)
        if not current:
            return {"status": "missing", "tenant_id": tenant_id}
        current["status"] = "promoted" if promote else "rolled_back"
        current["finished_at"] = int(time.time())
        self.state["rollout"]["history"].append(current)
        self.state["rollout"]["history"] = self.state["rollout"]["history"][-300:]
        self.state["rollout"]["active"].pop(tenant_id, None)
        return current

