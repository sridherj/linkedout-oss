# SPDX-License-Identifier: Apache-2.0
"""Repository for EnrichmentConfig entity."""
from typing import List, Optional

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from common.schemas.base_enums_schemas import SortOrder
from organization.enrichment_config.entities.enrichment_config_entity import EnrichmentConfigEntity
from organization.enrichment_config.schemas.enrichment_config_api_schema import EnrichmentConfigSortByFields
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class EnrichmentConfigRepository:
    """Repository for EnrichmentConfig entity. Organization-level, no tenant/bu scoping."""

    def __init__(self, session: Session):
        self._session = session

    def list_with_filters(
        self,
        limit: int = 20,
        offset: int = 0,
        sort_by: EnrichmentConfigSortByFields = EnrichmentConfigSortByFields.CREATED_AT,
        sort_order: SortOrder = SortOrder.DESC,
        app_user_id: Optional[str] = None,
        enrichment_mode: Optional[str] = None,
    ) -> List[EnrichmentConfigEntity]:
        query = self._session.query(EnrichmentConfigEntity)

        if app_user_id:
            query = query.filter(EnrichmentConfigEntity.app_user_id == app_user_id)
        if enrichment_mode:
            query = query.filter(EnrichmentConfigEntity.enrichment_mode == enrichment_mode)

        sort_column = getattr(EnrichmentConfigEntity, sort_by.value, EnrichmentConfigEntity.created_at)
        if sort_order == SortOrder.DESC:
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        return query.limit(limit).offset(offset).all()

    def count_with_filters(
        self,
        app_user_id: Optional[str] = None,
        enrichment_mode: Optional[str] = None,
    ) -> int:
        query = self._session.query(EnrichmentConfigEntity)

        if app_user_id:
            query = query.filter(EnrichmentConfigEntity.app_user_id == app_user_id)
        if enrichment_mode:
            query = query.filter(EnrichmentConfigEntity.enrichment_mode == enrichment_mode)

        return query.count()

    def create(self, entity: EnrichmentConfigEntity) -> EnrichmentConfigEntity:
        self._session.add(entity)
        self._session.flush()
        self._session.refresh(entity)
        return entity

    def get_by_id(self, entity_id: str) -> Optional[EnrichmentConfigEntity]:
        return (
            self._session.query(EnrichmentConfigEntity)
            .filter(EnrichmentConfigEntity.id == entity_id)
            .one_or_none()
        )

    def update(self, entity: EnrichmentConfigEntity) -> EnrichmentConfigEntity:
        self._session.merge(entity)
        self._session.flush()
        self._session.refresh(entity)
        return entity

    def delete(self, entity: EnrichmentConfigEntity) -> None:
        self._session.delete(entity)
