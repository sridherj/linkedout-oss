# SPDX-License-Identifier: Apache-2.0
"""Repository for FundingRound entity (shared, no tenant/BU scoping)."""
from typing import List, Optional

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from common.schemas.base_enums_schemas import SortOrder
from linkedout.funding.entities.funding_round_entity import FundingRoundEntity
from linkedout.funding.schemas.funding_round_api_schema import FundingRoundSortByFields
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class FundingRoundRepository:

    def __init__(self, session: Session):
        self._session = session

    def list_with_filters(
        self,
        limit: int = 20,
        offset: int = 0,
        sort_by: FundingRoundSortByFields = FundingRoundSortByFields.CREATED_AT,
        sort_order: SortOrder = SortOrder.DESC,
        company_id: Optional[str] = None,
        round_type: Optional[str] = None,
    ) -> List[FundingRoundEntity]:
        query = self._session.query(FundingRoundEntity)
        if company_id:
            query = query.filter(FundingRoundEntity.company_id == company_id)
        if round_type:
            query = query.filter(FundingRoundEntity.round_type == round_type)

        sort_column = getattr(FundingRoundEntity, sort_by, FundingRoundEntity.created_at)
        if sort_order == SortOrder.DESC:
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        return query.limit(limit).offset(offset).all()

    def count_with_filters(
        self,
        company_id: Optional[str] = None,
        round_type: Optional[str] = None,
    ) -> int:
        query = self._session.query(FundingRoundEntity)
        if company_id:
            query = query.filter(FundingRoundEntity.company_id == company_id)
        if round_type:
            query = query.filter(FundingRoundEntity.round_type == round_type)
        return query.count()

    def create(self, entity: FundingRoundEntity) -> FundingRoundEntity:
        self._session.add(entity)
        self._session.flush()
        self._session.refresh(entity)
        return entity

    def get_by_id(self, entity_id: str) -> Optional[FundingRoundEntity]:
        return (
            self._session.query(FundingRoundEntity)
            .filter(FundingRoundEntity.id == entity_id)
            .one_or_none()
        )

    def update(self, entity: FundingRoundEntity) -> FundingRoundEntity:
        self._session.merge(entity)
        self._session.flush()
        self._session.refresh(entity)
        return entity

    def delete(self, entity: FundingRoundEntity) -> None:
        self._session.delete(entity)
