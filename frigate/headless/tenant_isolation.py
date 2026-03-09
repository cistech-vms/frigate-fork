import time
from typing import Any


class TenantQuotaManager:
    def __init__(self) -> None:
        self.quotas: dict[str, dict[str, int]] = {}
        self.usage: dict[str, dict[str, int]] = {}
        self.audit: list[dict[str, Any]] = []

    def set_quota(self, tenant_id: str, quota: dict[str, int]) -> dict[str, Any]:
        self.quotas[tenant_id] = {k: int(v) for k, v in quota.items()}
        return self.quotas[tenant_id]

    def consume(self, tenant_id: str, resource: str, amount: int = 1) -> tuple[bool, dict[str, Any]]:
        amount = max(1, int(amount))
        quota = self.quotas.get(tenant_id, {})
        limit = int(quota.get(resource, 0))
        usage = self.usage.setdefault(tenant_id, {})
        current = int(usage.get(resource, 0))
        next_value = current + amount
        allowed = limit <= 0 or next_value <= limit
        if allowed:
            usage[resource] = next_value
        else:
            self.audit.append(
                {
                    "tenant_id": tenant_id,
                    "resource": resource,
                    "amount": amount,
                    "limit": limit,
                    "current": current,
                    "ts": int(time.time()),
                    "event": "quota_exceeded",
                }
            )
            self.audit = self.audit[-500:]
        return allowed, {
            "tenant_id": tenant_id,
            "resource": resource,
            "limit": limit,
            "current": usage.get(resource, current),
            "allowed": allowed,
        }

    def snapshot(self) -> dict[str, Any]:
        return {"quotas": self.quotas, "usage": self.usage, "audit": self.audit}
