from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .control_plane_state import DesiredTenantState, OperationalTenantState
from .state_persistence import HeadlessStateStore


class TenantStateRepository(Protocol):
    def load_desired_state(self, tenant_id: str) -> DesiredTenantState: ...

    def save_desired_state(self, state: DesiredTenantState) -> dict: ...

    def load_operational_state(self, tenant_id: str) -> OperationalTenantState: ...

    def save_operational_state(self, state: OperationalTenantState) -> dict: ...


@dataclass
class HeadlessStateRepositoryAdapter:
    store: HeadlessStateStore

    def load_desired_state(self, tenant_id: str) -> DesiredTenantState:
        payload = self.store.desired_state()
        tenants = payload.get("tenants", {}) if isinstance(payload, dict) else {}
        selected = tenants.get(tenant_id, {}) if isinstance(tenants, dict) else {}
        return DesiredTenantState.from_dict(tenant_id, selected)

    def save_desired_state(self, state: DesiredTenantState) -> dict:
        payload = self.store.desired_state()
        tenants = payload.setdefault("tenants", {}) if isinstance(payload, dict) else {}
        if not isinstance(tenants, dict):
            tenants = {}
            payload["tenants"] = tenants
        tenants[state.tenant_id] = state.to_dict()
        return self.store.put_desired_state(payload)

    def load_operational_state(self, tenant_id: str) -> OperationalTenantState:
        payload = self.store.operational_state()
        tenants = payload.get("tenants", {}) if isinstance(payload, dict) else {}
        selected = tenants.get(tenant_id, {}) if isinstance(tenants, dict) else {}
        return OperationalTenantState.from_dict(tenant_id, selected)

    def save_operational_state(self, state: OperationalTenantState) -> dict:
        payload = self.store.operational_state()
        tenants = payload.setdefault("tenants", {}) if isinstance(payload, dict) else {}
        if not isinstance(tenants, dict):
            tenants = {}
            payload["tenants"] = tenants
        tenants[state.tenant_id] = state.to_dict()
        return self.store.put_operational_state(payload)
