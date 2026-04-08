# SPDX-License-Identifier: Apache-2.0
"""Controller for GrowthSignal endpoints (shared, no tenant/BU scoping)."""
import math
from typing import Annotated, Generator

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from common.controllers.base_controller_utils import create_service_dependency
from linkedout.funding.schemas.growth_signal_api_schema import (
    CreateGrowthSignalRequestSchema,
    CreateGrowthSignalResponseSchema,
    DeleteGrowthSignalByIdRequestSchema,
    GetGrowthSignalByIdRequestSchema,
    GetGrowthSignalByIdResponseSchema,
    ListGrowthSignalsRequestSchema,
    ListGrowthSignalsResponseSchema,
    UpdateGrowthSignalRequestSchema,
    UpdateGrowthSignalResponseSchema,
)
from linkedout.funding.services.growth_signal_service import GrowthSignalService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

growth_signals_router = APIRouter(
    prefix='/growth-signals',
    tags=['growth-signals'],
)


def _get_service() -> Generator[GrowthSignalService, None, None]:
    yield from create_service_dependency(GrowthSignalService, DbSessionType.READ)


def _get_write_service() -> Generator[GrowthSignalService, None, None]:
    yield from create_service_dependency(GrowthSignalService, DbSessionType.WRITE)


@growth_signals_router.get(
    '',
    response_model=ListGrowthSignalsResponseSchema,
    summary='List growth signals with filtering and pagination',
)
def list_growth_signals(
    request: Request,
    list_request: Annotated[ListGrowthSignalsRequestSchema, Query()],
    service: GrowthSignalService = Depends(_get_service),
) -> ListGrowthSignalsResponseSchema:
    growth_signals, total = service.list_growth_signals(list_request)
    page_count = math.ceil(total / list_request.limit) if total > 0 else 1
    return ListGrowthSignalsResponseSchema(
        growth_signals=growth_signals,
        total=total,
        limit=list_request.limit,
        offset=list_request.offset,
        page_count=page_count,
    )


@growth_signals_router.post(
    '',
    status_code=201,
    response_model=CreateGrowthSignalResponseSchema,
    summary='Create a new growth signal',
)
def create_growth_signal(
    request: Request,
    create_request: Annotated[CreateGrowthSignalRequestSchema, Body()],
    service: GrowthSignalService = Depends(_get_write_service),
) -> CreateGrowthSignalResponseSchema:
    created = service.create_growth_signal(create_request)
    return CreateGrowthSignalResponseSchema(growth_signal=created)


@growth_signals_router.patch(
    '/{growth_signal_id}',
    response_model=UpdateGrowthSignalResponseSchema,
    summary='Update a growth signal',
)
def update_growth_signal(
    request: Request,
    growth_signal_id: str,
    update_request: Annotated[UpdateGrowthSignalRequestSchema, Body()],
    service: GrowthSignalService = Depends(_get_write_service),
) -> UpdateGrowthSignalResponseSchema:
    update_request.growth_signal_id = growth_signal_id
    try:
        updated = service.update_growth_signal(update_request)
        return UpdateGrowthSignalResponseSchema(growth_signal=updated)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@growth_signals_router.get(
    '/{growth_signal_id}',
    response_model=GetGrowthSignalByIdResponseSchema,
    summary='Get a growth signal by ID',
)
def get_growth_signal_by_id(
    growth_signal_id: str,
    service: GrowthSignalService = Depends(_get_service),
) -> GetGrowthSignalByIdResponseSchema:
    req = GetGrowthSignalByIdRequestSchema(growth_signal_id=growth_signal_id)
    result = service.get_growth_signal_by_id(req)
    if not result:
        raise HTTPException(status_code=404, detail=f'GrowthSignal {growth_signal_id} not found')
    return GetGrowthSignalByIdResponseSchema(growth_signal=result)


@growth_signals_router.delete(
    '/{growth_signal_id}',
    status_code=204,
    summary='Delete a growth signal',
)
def delete_growth_signal_by_id(
    growth_signal_id: str,
    service: GrowthSignalService = Depends(_get_write_service),
) -> None:
    try:
        req = DeleteGrowthSignalByIdRequestSchema(growth_signal_id=growth_signal_id)
        service.delete_growth_signal_by_id(req)
        return Response(status_code=204)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
