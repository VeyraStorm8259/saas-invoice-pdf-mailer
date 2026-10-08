from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AccountState(StrEnum):
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    SUSPENDED = "suspended"


@dataclass
class Tenant:
    tenant_id: str
    legal_name: str
    billing_email: str
    state: AccountState = AccountState.ONBOARDING


class TenantLedger:
    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}

    def onboard(self, tenant: Tenant) -> Tenant:
        self._tenants[tenant.tenant_id] = tenant
        return tenant

    def set_state(self, tenant_id: str, state: AccountState) -> Tenant:
        tenant = self.get(tenant_id)
        tenant.state = state
        return tenant

    def get(self, tenant_id: str) -> Tenant:
        try:
            return self._tenants[tenant_id]
        except KeyError as exc:
            raise LookupError(f"Unknown tenant: {tenant_id}") from exc

