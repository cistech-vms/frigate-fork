import hashlib
import time
from typing import Any


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "***"
    return f"{value[:3]}***{value[-2:]}"


class SecretRotationManager:
    def __init__(self) -> None:
        self.state: dict[str, Any] = {
            "active": {},
            "previous": {},
            "history": [],
        }

    def rotate(self, name: str, new_value: str) -> dict[str, Any]:
        old_value = self.state["active"].get(name)
        if old_value:
            self.state["previous"][name] = old_value
        self.state["active"][name] = new_value
        entry = {
            "name": name,
            "rotated_at": int(time.time()),
            "fingerprint": hashlib.sha256(new_value.encode("utf-8")).hexdigest()[:12],
        }
        self.state["history"].append(entry)
        self.state["history"] = self.state["history"][-500:]
        return entry

    def revoke_previous(self, name: str) -> dict[str, Any]:
        self.state["previous"].pop(name, None)
        return {"name": name, "revoked_at": int(time.time())}

    def snapshot(self) -> dict[str, Any]:
        return {
            "active": {k: mask_secret(v) for k, v in self.state["active"].items()},
            "previous": {k: mask_secret(v) for k, v in self.state["previous"].items()},
            "history": self.state["history"],
        }
