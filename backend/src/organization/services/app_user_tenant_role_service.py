# SPDX-License-Identifier: Apache-2.0
"""Service for AppUserTenantRole - custom (not BaseService)."""
from typing import List

from sqlalchemy.orm import Session

from organization.entities.app_user_tenant_role_entity import AppUserTenantRoleEntity
from organization.repositories.app_user_tenant_role_repository import AppUserTenantRoleRepository
from organization.schemas.app_user_tenant_role_schema import AppUserTenantRoleSchema


class AppUserTenantRoleService:
    """Custom service for user-tenant role mapping."""

    def __init__(self, session: Session):
        self._session = session
        self._repository = AppUserTenantRoleRepository(session)

    def has_tenant_access(self, user_id: str, tenant_id: str) -> bool:
        return self._repository.has_tenant_access(user_id, tenant_id)

    def get_roles(self, user_id: str, tenant_id: str) -> List[str]:
        entities = self._repository.get_roles_for_user_tenant(user_id, tenant_id)
        return [e.role for e in entities]

    def assign_role(self, user_id: str, tenant_id: str, role: str) -> AppUserTenantRoleSchema:
        entity = AppUserTenantRoleEntity(
            app_user_id=user_id, tenant_id=tenant_id, role=role
        )
        created = self._repository.create(entity)
        return AppUserTenantRoleSchema.model_validate(created)
