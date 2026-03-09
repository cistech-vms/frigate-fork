from typing import Any


def default_runbooks() -> dict[str, Any]:
    return {
        "storage_offline": {
            "severity": "high",
            "triage": [
                "Confirm object storage endpoint reachability",
                "Check storage sync backlog and dead letters",
                "Switch provider to local if outage persists",
            ],
            "recover": [
                "Apply temporary local storage config",
                "Run storage reconciler",
                "Validate backlog drain under threshold",
            ],
            "escalation": "Escalate if backlog > 10k or dead_letter growth continues for 15min",
        },
        "queue_accumulation": {
            "severity": "medium",
            "triage": [
                "Inspect event delivery pending queue",
                "Validate webhook target latency/error",
                "Check CPU saturation and readiness mode",
            ],
            "recover": [
                "Enable throttling on non-critical writes",
                "Trigger self-healing reconcile",
                "Purge stale low-priority events if needed",
            ],
            "escalation": "Escalate if pending queue > 5k for 10min",
        },
        "degraded_node": {
            "severity": "high",
            "triage": [
                "Check readyz reasons/warnings",
                "Inspect camera process pids and fps",
                "Review rate limit and security audit spikes",
            ],
            "recover": [
                "Activate read-only degraded mode",
                "Restart delivery/sync workers",
                "Restore normal mode after 2 healthy cycles",
            ],
            "escalation": "Escalate if node not ready > 5min",
        },
    }
