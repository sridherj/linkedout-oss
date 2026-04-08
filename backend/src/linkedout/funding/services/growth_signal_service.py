# SPDX-License-Identifier: Apache-2.0
"""Service for GrowthSignal entity (shared, no tenant/BU scoping)."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from linkedout.funding.entities.growth_signal_entity import GrowthSignalEntity
from linkedout.funding.repositories.growth_signal_repository import GrowthSignalRepository
from linkedout.funding.schemas.growth_signal_api_schema import (
    CreateGrowthSignalRequestSchema,
    DeleteGrowthSignalByIdRequestSchema,
    GetGrowthSignalByIdRequestSchema,
    ListGrowthSignalsRequestSchema,
    UpdateGrowthSignalRequestSchema,
)
from linkedout.funding.schemas.growth_signal_schema import GrowthSignalSchema
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class GrowthSignalService:

    def __init__(self, session: Session):
        self._session = session
        self._repository = GrowthSignalRepository(session)

    def list_growth_signals(
        self, list_request: ListGrowthSignalsRequestSchema
    ) -> Tuple[List[GrowthSignalSchema], int]:
        entities = self._repository.list_with_filters(
            limit=list_request.limit,
            offset=list_request.offset,
            sort_by=list_request.sort_by,
            sort_order=list_request.sort_order,
            company_id=list_request.company_id,
            signal_type=list_request.signal_type,
        )
        total = self._repository.count_with_filters(
            company_id=list_request.company_id,
            signal_type=list_request.signal_type,
        )
        return [GrowthSignalSchema.model_validate(e) for e in entities], total

    def create_growth_signal(self, req: CreateGrowthSignalRequestSchema) -> GrowthSignalSchema:
        entity = GrowthSignalEntity(
            company_id=req.company_id,
            signal_type=req.signal_type,
            signal_date=req.signal_date,
            value_numeric=req.value_numeric,
            value_text=req.value_text,
            source_url=req.source_url,
            confidence=req.confidence,
            source=req.source,
            notes=req.notes,
        )
        created = self._repository.create(entity)
        return GrowthSignalSchema.model_validate(created)

    def update_growth_signal(self, req: UpdateGrowthSignalRequestSchema) -> GrowthSignalSchema:
        entity = self._repository.get_by_id(req.growth_signal_id)
        if not entity:
            raise ValueError(f'GrowthSignal not found: {req.growth_signal_id}')

        if req.signal_type is not None:
            entity.signal_type = req.signal_type
        if req.signal_date is not None:
            entity.signal_date = req.signal_date
        if req.value_numeric is not None:
            entity.value_numeric = req.value_numeric
        if req.value_text is not None:
            entity.value_text = req.value_text
        if req.source_url is not None:
            entity.source_url = req.source_url
        if req.confidence is not None:
            entity.confidence = req.confidence
        if req.source is not None:
            entity.source = req.source
        if req.notes is not None:
            entity.notes = req.notes

        updated = self._repository.update(entity)
        return GrowthSignalSchema.model_validate(updated)

    def get_growth_signal_by_id(self, req: GetGrowthSignalByIdRequestSchema) -> Optional[GrowthSignalSchema]:
        entity = self._repository.get_by_id(req.growth_signal_id)
        if not entity:
            return None
        return GrowthSignalSchema.model_validate(entity)

    def delete_growth_signal_by_id(self, req: DeleteGrowthSignalByIdRequestSchema) -> None:
        entity = self._repository.get_by_id(req.growth_signal_id)
        if not entity:
            raise ValueError(f'GrowthSignal not found: {req.growth_signal_id}')
        self._repository.delete(entity)
