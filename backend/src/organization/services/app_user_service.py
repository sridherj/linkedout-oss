# SPDX-License-Identifier: Apache-2.0
"""Service for AppUser - custom (not BaseService)."""
from typing import Optional

from sqlalchemy.orm import Session

from organization.entities.app_user_entity import AppUserEntity
from organization.repositories.app_user_repository import AppUserRepository
from organization.schemas.app_user_schema import AppUserSchema


class AppUserService:
    """Custom service - AppUser sits above tenant/BU scoping."""

    def __init__(self, session: Session):
        self._session = session
        self._repository = AppUserRepository(session)

    def get_by_auth_provider_id(self, auth_provider_id: str) -> Optional[AppUserSchema]:
        entity = self._repository.get_by_auth_provider_id(auth_provider_id)
        if not entity:
            return None
        return AppUserSchema.model_validate(entity)

    def get_by_email(self, email: str) -> Optional[AppUserSchema]:
        entity = self._repository.get_by_email(email)
        if not entity:
            return None
        return AppUserSchema.model_validate(entity)

    def create_user(self, email: str, name: Optional[str] = None,
                    auth_provider_id: Optional[str] = None) -> AppUserSchema:
        entity = AppUserEntity(
            email=email, name=name, auth_provider_id=auth_provider_id
        )
        created = self._repository.create(entity)
        return AppUserSchema.model_validate(created)
