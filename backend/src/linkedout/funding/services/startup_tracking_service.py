# SPDX-License-Identifier: Apache-2.0
"""Service for StartupTracking entity (shared, no tenant/BU scoping)."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from linkedout.funding.entities.startup_tracking_entity import StartupTrackingEntity
from linkedout.funding.repositories.startup_tracking_repository import StartupTrackingRepository
from linkedout.funding.schemas.startup_tracking_api_schema import (
    CreateStartupTrackingRequestSchema,
    DeleteStartupTrackingByIdRequestSchema,
    GetStartupTrackingByIdRequestSchema,
    ListStartupTrackingsRequestSchema,
    UpdateStartupTrackingRequestSchema,
)
from linkedout.funding.schemas.startup_tracking_schema import StartupTrackingSchema
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class StartupTrackingService:

    def __init__(self, session: Session):
        self._session = session
        self._repository = StartupTrackingRepository(session)

    def list_startup_trackings(
        self, list_request: ListStartupTrackingsRequestSchema
    ) -> Tuple[List[StartupTrackingSchema], int]:
        entities = self._repository.list_with_filters(
            limit=list_request.limit,
            offset=list_request.offset,
            sort_by=list_request.sort_by,
            sort_order=list_request.sort_order,
            company_id=list_request.company_id,
            watching=list_request.watching,
            vertical=list_request.vertical,
        )
        total = self._repository.count_with_filters(
            company_id=list_request.company_id,
            watching=list_request.watching,
            vertical=list_request.vertical,
        )
        return [StartupTrackingSchema.model_validate(e) for e in entities], total

    def create_startup_tracking(self, req: CreateStartupTrackingRequestSchema) -> StartupTrackingSchema:
        entity = StartupTrackingEntity(
            company_id=req.company_id,
            watching=req.watching,
            description=req.description,
            vertical=req.vertical,
            sub_category=req.sub_category,
            funding_stage=req.funding_stage,
            total_raised_usd=req.total_raised_usd,
            last_funding_date=req.last_funding_date,
            round_count=req.round_count,
            estimated_arr_usd=req.estimated_arr_usd,
            arr_signal_date=req.arr_signal_date,
            arr_confidence=req.arr_confidence,
            source=req.source,
            notes=req.notes,
        )
        created = self._repository.create(entity)
        return StartupTrackingSchema.model_validate(created)

    def update_startup_tracking(self, req: UpdateStartupTrackingRequestSchema) -> StartupTrackingSchema:
        entity = self._repository.get_by_id(req.startup_tracking_id)
        if not entity:
            raise ValueError(f'StartupTracking not found: {req.startup_tracking_id}')

        if req.watching is not None:
            entity.watching = req.watching
        if req.description is not None:
            entity.description = req.description
        if req.vertical is not None:
            entity.vertical = req.vertical
        if req.sub_category is not None:
            entity.sub_category = req.sub_category
        if req.funding_stage is not None:
            entity.funding_stage = req.funding_stage
        if req.total_raised_usd is not None:
            entity.total_raised_usd = req.total_raised_usd
        if req.last_funding_date is not None:
            entity.last_funding_date = req.last_funding_date
        if req.round_count is not None:
            entity.round_count = req.round_count
        if req.estimated_arr_usd is not None:
            entity.estimated_arr_usd = req.estimated_arr_usd
        if req.arr_signal_date is not None:
            entity.arr_signal_date = req.arr_signal_date
        if req.arr_confidence is not None:
            entity.arr_confidence = req.arr_confidence
        if req.source is not None:
            entity.source = req.source
        if req.notes is not None:
            entity.notes = req.notes

        updated = self._repository.update(entity)
        return StartupTrackingSchema.model_validate(updated)

    def get_startup_tracking_by_id(self, req: GetStartupTrackingByIdRequestSchema) -> Optional[StartupTrackingSchema]:
        entity = self._repository.get_by_id(req.startup_tracking_id)
        if not entity:
            return None
        return StartupTrackingSchema.model_validate(entity)

    def delete_startup_tracking_by_id(self, req: DeleteStartupTrackingByIdRequestSchema) -> None:
        entity = self._repository.get_by_id(req.startup_tracking_id)
        if not entity:
            raise ValueError(f'StartupTracking not found: {req.startup_tracking_id}')
        self._repository.delete(entity)
