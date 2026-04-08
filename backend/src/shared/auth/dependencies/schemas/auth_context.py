# SPDX-License-Identifier: Apache-2.0
"""Auth context schemas — Principal, Actor, Subject, AuthContext."""
from typing import Optional, List

from pydantic import BaseModel, Field

from shared.auth.dependencies.schemas.role_enums import TenantRole, BuRole


class Principal(BaseModel):
    """WHO is authenticated. Populated in Layer 1."""
    auth_provider_id: str = Field(..., description="Firebase UID, 'service_account:<name>', or 'api_key:<app_user_id>'")
    user_id: Optional[str] = Field(default=None, description="App user ID from DB (populated in Layer 2)")
    email: Optional[str] = Field(default=None, description="User email (populated in Layer 2)")
    name: Optional[str] = Field(default=None, description="User display name (populated in Layer 2)")


class Actor(BaseModel):
    """WHAT roles in current context. Populated in Layer 2."""
    id: str = Field(..., description="App user ID or service account ID")
    current_tenant_roles: List[TenantRole] = Field(default_factory=list)
    current_bu_roles: List[BuRole] = Field(default_factory=list)
    is_impersonating: bool = Field(default=False)

    def has_tenant_role(self, *roles: TenantRole) -> bool:
        return any(r in self.current_tenant_roles for r in roles)

    def has_bu_role(self, *roles: BuRole) -> bool:
        return any(r in self.current_bu_roles for r in roles)

    def is_tenant_admin(self) -> bool:
        return TenantRole.ADMIN in self.current_tenant_roles

    def is_bu_admin(self) -> bool:
        return BuRole.ADMIN in self.current_bu_roles

    def is_admin(self) -> bool:
        return self.is_tenant_admin() or self.is_bu_admin()


class Subject(BaseModel):
    """WHAT is being acted upon. Populated in Layer 2."""
    tenant_id: str
    bu_id: Optional[str] = None


class AuthContext(BaseModel):
    """Complete auth context, progressively enriched through the 3-layer chain."""
    principal: Principal
    actor: Optional[Actor] = None
    subject: Optional[Subject] = None

    def has_tenant_role(self, *roles: TenantRole) -> bool:
        return self.actor.has_tenant_role(*roles) if self.actor else False

    def has_bu_role(self, *roles: BuRole) -> bool:
        return self.actor.has_bu_role(*roles) if self.actor else False

    def is_admin(self) -> bool:
        return self.actor.is_admin() if self.actor else False

    def is_tenant_admin(self) -> bool:
        return self.actor.is_tenant_admin() if self.actor else False

    def is_bu_admin(self) -> bool:
        return self.actor.is_bu_admin() if self.actor else False

    @property
    def is_service_account(self) -> bool:
        return self.principal.auth_provider_id.startswith("service_account:")

    @property
    def is_api_key_auth(self) -> bool:
        return self.principal.auth_provider_id.startswith("api_key:")
