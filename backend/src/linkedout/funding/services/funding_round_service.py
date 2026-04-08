# SPDX-License-Identifier: Apache-2.0
"""Service for FundingRound entity (shared, no tenant/BU scoping)."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from linkedout.funding.entities.funding_round_entity import FundingRoundEntity
from linkedout.funding.repositories.funding_round_repository import FundingRoundRepository
from linkedout.funding.schemas.funding_round_api_schema import (
    CreateFundingRoundRequestSchema,
    DeleteFundingRoundByIdRequestSchema,
    GetFundingRoundByIdRequestSchema,
    ListFundingRoundsRequestSchema,
    UpdateFundingRoundRequestSchema,
)
from linkedout.funding.schemas.funding_round_schema import FundingRoundSchema
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class FundingRoundService:

    def __init__(self, session: Session):
        self._session = session
        self._repository = FundingRoundRepository(session)

    def list_funding_rounds(
        self, list_request: ListFundingRoundsRequestSchema
    ) -> Tuple[List[FundingRoundSchema], int]:
        entities = self._repository.list_with_filters(
            limit=list_request.limit,
            offset=list_request.offset,
            sort_by=list_request.sort_by,
            sort_order=list_request.sort_order,
            company_id=list_request.company_id,
            round_type=list_request.round_type,
        )
        total = self._repository.count_with_filters(
            company_id=list_request.company_id,
            round_type=list_request.round_type,
        )
        return [FundingRoundSchema.model_validate(e) for e in entities], total

    def create_funding_round(self, req: CreateFundingRoundRequestSchema) -> FundingRoundSchema:
        entity = FundingRoundEntity(
            company_id=req.company_id,
            round_type=req.round_type,
            announced_on=req.announced_on,
            amount_usd=req.amount_usd,
            lead_investors=req.lead_investors,
            all_investors=req.all_investors,
            source_url=req.source_url,
            confidence=req.confidence,
            source=req.source,
            notes=req.notes,
        )
        created = self._repository.create(entity)
        return FundingRoundSchema.model_validate(created)

    def update_funding_round(self, req: UpdateFundingRoundRequestSchema) -> FundingRoundSchema:
        entity = self._repository.get_by_id(req.funding_round_id)
        if not entity:
            raise ValueError(f'FundingRound not found: {req.funding_round_id}')

        if req.round_type is not None:
            entity.round_type = req.round_type
        if req.announced_on is not None:
            entity.announced_on = req.announced_on
        if req.amount_usd is not None:
            entity.amount_usd = req.amount_usd
        if req.lead_investors is not None:
            entity.lead_investors = req.lead_investors
        if req.all_investors is not None:
            entity.all_investors = req.all_investors
        if req.source_url is not None:
            entity.source_url = req.source_url
        if req.confidence is not None:
            entity.confidence = req.confidence
        if req.source is not None:
            entity.source = req.source
        if req.notes is not None:
            entity.notes = req.notes

        updated = self._repository.update(entity)
        return FundingRoundSchema.model_validate(updated)

    def get_funding_round_by_id(self, req: GetFundingRoundByIdRequestSchema) -> Optional[FundingRoundSchema]:
        entity = self._repository.get_by_id(req.funding_round_id)
        if not entity:
            return None
        return FundingRoundSchema.model_validate(entity)

    def delete_funding_round_by_id(self, req: DeleteFundingRoundByIdRequestSchema) -> None:
        entity = self._repository.get_by_id(req.funding_round_id)
        if not entity:
            raise ValueError(f'FundingRound not found: {req.funding_round_id}')
        self._repository.delete(entity)
