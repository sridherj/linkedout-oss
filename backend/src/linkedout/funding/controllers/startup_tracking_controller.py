# SPDX-License-Identifier: Apache-2.0
"""Controller for StartupTracking endpoints (shared, no tenant/BU scoping)."""
import math
from typing import Annotated, Generator

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from common.controllers.base_controller_utils import create_service_dependency
from linkedout.funding.schemas.startup_tracking_api_schema import (
    CreateStartupTrackingRequestSchema,
    CreateStartupTrackingResponseSchema,
    DeleteStartupTrackingByIdRequestSchema,
    GetStartupTrackingByIdRequestSchema,
    GetStartupTrackingByIdResponseSchema,
    ListStartupTrackingsRequestSchema,
    ListStartupTrackingsResponseSchema,
    UpdateStartupTrackingRequestSchema,
    UpdateStartupTrackingResponseSchema,
)
from linkedout.funding.services.startup_tracking_service import StartupTrackingService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

startup_trackings_router = APIRouter(
    prefix='/startup-trackings',
    tags=['startup-trackings'],
)


def _get_service() -> Generator[StartupTrackingService, None, None]:
    yield from create_service_dependency(StartupTrackingService, DbSessionType.READ)


def _get_write_service() -> Generator[StartupTrackingService, None, None]:
    yield from create_service_dependency(StartupTrackingService, DbSessionType.WRITE)


@startup_trackings_router.get(
    '',
    response_model=ListStartupTrackingsResponseSchema,
    summary='List startup trackings with filtering and pagination',
)
def list_startup_trackings(
    request: Request,
    list_request: Annotated[ListStartupTrackingsRequestSchema, Query()],
    service: StartupTrackingService = Depends(_get_service),
) -> ListStartupTrackingsResponseSchema:
    startup_trackings, total = service.list_startup_trackings(list_request)
    page_count = math.ceil(total / list_request.limit) if total > 0 else 1
    return ListStartupTrackingsResponseSchema(
        startup_trackings=startup_trackings,
        total=total,
        limit=list_request.limit,
        offset=list_request.offset,
        page_count=page_count,
    )


@startup_trackings_router.post(
    '',
    status_code=201,
    response_model=CreateStartupTrackingResponseSchema,
    summary='Create a new startup tracking',
)
def create_startup_tracking(
    request: Request,
    create_request: Annotated[CreateStartupTrackingRequestSchema, Body()],
    service: StartupTrackingService = Depends(_get_write_service),
) -> CreateStartupTrackingResponseSchema:
    created = service.create_startup_tracking(create_request)
    return CreateStartupTrackingResponseSchema(startup_tracking=created)


@startup_trackings_router.patch(
    '/{startup_tracking_id}',
    response_model=UpdateStartupTrackingResponseSchema,
    summary='Update a startup tracking',
)
def update_startup_tracking(
    request: Request,
    startup_tracking_id: str,
    update_request: Annotated[UpdateStartupTrackingRequestSchema, Body()],
    service: StartupTrackingService = Depends(_get_write_service),
) -> UpdateStartupTrackingResponseSchema:
    update_request.startup_tracking_id = startup_tracking_id
    try:
        updated = service.update_startup_tracking(update_request)
        return UpdateStartupTrackingResponseSchema(startup_tracking=updated)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@startup_trackings_router.get(
    '/{startup_tracking_id}',
    response_model=GetStartupTrackingByIdResponseSchema,
    summary='Get a startup tracking by ID',
)
def get_startup_tracking_by_id(
    startup_tracking_id: str,
    service: StartupTrackingService = Depends(_get_service),
) -> GetStartupTrackingByIdResponseSchema:
    req = GetStartupTrackingByIdRequestSchema(startup_tracking_id=startup_tracking_id)
    result = service.get_startup_tracking_by_id(req)
    if not result:
        raise HTTPException(status_code=404, detail=f'StartupTracking {startup_tracking_id} not found')
    return GetStartupTrackingByIdResponseSchema(startup_tracking=result)


@startup_trackings_router.delete(
    '/{startup_tracking_id}',
    status_code=204,
    summary='Delete a startup tracking',
)
def delete_startup_tracking_by_id(
    startup_tracking_id: str,
    service: StartupTrackingService = Depends(_get_write_service),
) -> None:
    try:
        req = DeleteStartupTrackingByIdRequestSchema(startup_tracking_id=startup_tracking_id)
        service.delete_startup_tracking_by_id(req)
        return Response(status_code=204)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
