# SPDX-License-Identifier: Apache-2.0
"""Repository for GrowthSignal entity (shared, no tenant/BU scoping)."""
from typing import List, Optional

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from common.schemas.base_enums_schemas import SortOrder
from linkedout.funding.entities.growth_signal_entity import GrowthSignalEntity
from linkedout.funding.schemas.growth_signal_api_schema import GrowthSignalSortByFields
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class GrowthSignalRepository:

    def __init__(self, session: Session):
        self._session = session

    def list_with_filters(
        self,
        limit: int = 20,
        offset: int = 0,
        sort_by: GrowthSignalSortByFields = GrowthSignalSortByFields.CREATED_AT,
        sort_order: SortOrder = SortOrder.DESC,
        company_id: Optional[str] = None,
        signal_type: Optional[str] = None,
    ) -> List[GrowthSignalEntity]:
        query = self._session.query(GrowthSignalEntity)
        if company_id:
            query = query.filter(GrowthSignalEntity.company_id == company_id)
        if signal_type:
            query = query.filter(GrowthSignalEntity.signal_type == signal_type)

        sort_column = getattr(GrowthSignalEntity, sort_by, GrowthSignalEntity.created_at)
        if sort_order == SortOrder.DESC:
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        return query.limit(limit).offset(offset).all()

    def count_with_filters(
        self,
        company_id: Optional[str] = None,
        signal_type: Optional[str] = None,
    ) -> int:
        query = self._session.query(GrowthSignalEntity)
        if company_id:
            query = query.filter(GrowthSignalEntity.company_id == company_id)
        if signal_type:
            query = query.filter(GrowthSignalEntity.signal_type == signal_type)
        return query.count()

    def create(self, entity: GrowthSignalEntity) -> GrowthSignalEntity:
        self._session.add(entity)
        self._session.flush()
        self._session.refresh(entity)
        return entity

    def get_by_id(self, entity_id: str) -> Optional[GrowthSignalEntity]:
        return (
            self._session.query(GrowthSignalEntity)
            .filter(GrowthSignalEntity.id == entity_id)
            .one_or_none()
        )

    def update(self, entity: GrowthSignalEntity) -> GrowthSignalEntity:
        self._session.merge(entity)
        self._session.flush()
        self._session.refresh(entity)
        return entity

    def delete(self, entity: GrowthSignalEntity) -> None:
        self._session.delete(entity)
