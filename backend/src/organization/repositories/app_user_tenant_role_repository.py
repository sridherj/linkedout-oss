# SPDX-License-Identifier: Apache-2.0
"""Repository for AppUserTenantRole entity - custom (not BaseRepository)."""
from typing import List, Optional

from sqlalchemy.orm import Session

from organization.entities.app_user_tenant_role_entity import AppUserTenantRoleEntity
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class AppUserTenantRoleRepository:
    """Custom repository - not tenant/BU-scoped in the standard way."""

    def __init__(self, session: Session):
        self._session = session

    def get_roles_for_user_tenant(
        self, app_user_id: str, tenant_id: str
    ) -> List[AppUserTenantRoleEntity]:
        return self._session.query(AppUserTenantRoleEntity).filter(
            AppUserTenantRoleEntity.app_user_id == app_user_id,
            AppUserTenantRoleEntity.tenant_id == tenant_id,
        ).all()

    def has_tenant_access(self, app_user_id: str, tenant_id: str) -> bool:
        result = self._session.query(AppUserTenantRoleEntity).filter(
            AppUserTenantRoleEntity.app_user_id == app_user_id,
            AppUserTenantRoleEntity.tenant_id == tenant_id,
        ).first()
        return result is not None

    def create(self, entity: AppUserTenantRoleEntity) -> AppUserTenantRoleEntity:
        self._session.add(entity)
        self._session.flush()
        self._session.refresh(entity)
        return entity
