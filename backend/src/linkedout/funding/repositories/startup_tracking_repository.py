# SPDX-License-Identifier: Apache-2.0
"""Repository for StartupTracking entity (shared, no tenant/BU scoping)."""
from typing import List, Optional

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from common.schemas.base_enums_schemas import SortOrder
from linkedout.funding.entities.startup_tracking_entity import StartupTrackingEntity
from linkedout.funding.schemas.startup_tracking_api_schema import StartupTrackingSortByFields
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class StartupTrackingRepository:

    def __init__(self, session: Session):
        self._session = session

    def list_with_filters(
        self,
        limit: int = 20,
        offset: int = 0,
        sort_by: StartupTrackingSortByFields = StartupTrackingSortByFields.CREATED_AT,
        sort_order: SortOrder = SortOrder.DESC,
        company_id: Optional[str] = None,
        watching: Optional[bool] = None,
        vertical: Optional[str] = None,
    ) -> List[StartupTrackingEntity]:
        query = self._session.query(StartupTrackingEntity)
        if company_id:
            query = query.filter(StartupTrackingEntity.company_id == company_id)
        if watching is not None:
            query = query.filter(StartupTrackingEntity.watching == watching)
        if vertical:
            query = query.filter(StartupTrackingEntity.vertical == vertical)

        sort_column = getattr(StartupTrackingEntity, sort_by, StartupTrackingEntity.created_at)
        if sort_order == SortOrder.DESC:
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        return query.limit(limit).offset(offset).all()

    def count_with_filters(
        self,
        company_id: Optional[str] = None,
        watching: Optional[bool] = None,
        vertical: Optional[str] = None,
    ) -> int:
        query = self._session.query(StartupTrackingEntity)
        if company_id:
            query = query.filter(StartupTrackingEntity.company_id == company_id)
        if watching is not None:
            query = query.filter(StartupTrackingEntity.watching == watching)
        if vertical:
            query = query.filter(StartupTrackingEntity.vertical == vertical)
        return query.count()

    def create(self, entity: StartupTrackingEntity) -> StartupTrackingEntity:
        self._session.add(entity)
        self._session.flush()
        self._session.refresh(entity)
        return entity

    def get_by_id(self, entity_id: str) -> Optional[StartupTrackingEntity]:
        return (
            self._session.query(StartupTrackingEntity)
            .filter(StartupTrackingEntity.id == entity_id)
            .one_or_none()
        )

    def update(self, entity: StartupTrackingEntity) -> StartupTrackingEntity:
        self._session.merge(entity)
        self._session.flush()
        self._session.refresh(entity)
        return entity

    def delete(self, entity: StartupTrackingEntity) -> None:
        self._session.delete(entity)
