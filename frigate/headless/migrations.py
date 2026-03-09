import time
from typing import Any


class MigrationManager:
    def __init__(self) -> None:
        self.state: dict[str, Any] = {
            "schema_version": 1,
            "history": [],
        }

    def apply(self, target_version: int, backup_id: str | None = None) -> dict[str, Any]:
        if target_version < 1:
            raise ValueError("invalid_target_version")
        previous = int(self.state.get("schema_version", 1))
        self.state["schema_version"] = target_version
        item = {
            "from": previous,
            "to": target_version,
            "backup_id": backup_id,
            "applied_at": int(time.time()),
            "status": "applied",
        }
        self.state["history"].append(item)
        self.state["history"] = self.state["history"][-500:]
        return item

    def rollback(self, target_version: int) -> dict[str, Any]:
        if target_version < 1:
            raise ValueError("invalid_target_version")
        previous = int(self.state.get("schema_version", 1))
        self.state["schema_version"] = target_version
        item = {
            "from": previous,
            "to": target_version,
            "rolled_back_at": int(time.time()),
            "status": "rolled_back",
        }
        self.state["history"].append(item)
        self.state["history"] = self.state["history"][-500:]
        return item

    def snapshot(self) -> dict[str, Any]:
        return self.state
