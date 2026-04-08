# SPDX-License-Identifier: Apache-2.0
"""Repository for AppUser entity - custom (not BaseRepository)."""
from typing import Optional

from sqlalchemy.orm import Session

from organization.entities.app_user_entity import AppUserEntity
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class AppUserRepository:
    """Custom repository - AppUser is not tenant/BU-scoped."""

    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, user_id: str) -> Optional[AppUserEntity]:
        return self._session.query(AppUserEntity).filter(
            AppUserEntity.id == user_id
        ).one_or_none()

    def get_by_email(self, email: str) -> Optional[AppUserEntity]:
        return self._session.query(AppUserEntity).filter(
            AppUserEntity.email == email
        ).one_or_none()

    def get_by_auth_provider_id(self, auth_provider_id: str) -> Optional[AppUserEntity]:
        return self._session.query(AppUserEntity).filter(
            AppUserEntity.auth_provider_id == auth_provider_id
        ).one_or_none()

    def create(self, entity: AppUserEntity) -> AppUserEntity:
        self._session.add(entity)
        self._session.flush()
        self._session.refresh(entity)
        return entity
