import time
from typing import Any


class DisasterRecoveryPlan:
    def __init__(self) -> None:
        self.state: dict[str, Any] = {
            "scenarios": [
                "single_node_failure",
                "storage_region_outage",
                "control_plane_unreachable",
            ],
            "exercises": [],
        }

    def record_exercise(
        self, scenario: str, rpo_sec: int, rto_sec: int, success: bool
    ) -> dict[str, Any]:
        item = {
            "scenario": scenario,
            "rpo_sec": int(rpo_sec),
            "rto_sec": int(rto_sec),
            "success": bool(success),
            "ts": int(time.time()),
        }
        self.state["exercises"].append(item)
        self.state["exercises"] = self.state["exercises"][-300:]
        return item

    def snapshot(self) -> dict[str, Any]:
        return self.state
