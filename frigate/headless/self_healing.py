import time
from typing import Any


def init_self_healing_state() -> dict[str, Any]:
    return {
        "enabled": True,
        "cooldown_sec": 30,
        "last_recovery_ts": 0,
        "recoveries": [],
        "chaos_events": [],
    }


def register_chaos_event(state: dict[str, Any], scenario: str) -> dict[str, Any]:
    event = {"scenario": scenario, "ts": int(time.time())}
    events = state.get("chaos_events", [])
    events.append(event)
    state["chaos_events"] = events[-200:]
    return event


def should_recover(state: dict[str, Any], now_ts: float | None = None) -> bool:
    now_ts = now_ts or time.time()
    if not state.get("enabled", True):
        return False
    last = float(state.get("last_recovery_ts", 0))
    cooldown = max(1, int(state.get("cooldown_sec", 30)))
    return (now_ts - last) >= cooldown


def register_recovery(state: dict[str, Any], action: str, reason: str) -> dict[str, Any]:
    item = {
        "action": action,
        "reason": reason,
        "ts": int(time.time()),
    }
    items = state.get("recoveries", [])
    items.append(item)
    state["recoveries"] = items[-200:]
    state["last_recovery_ts"] = int(time.time())
    return item
