# SPDX-License-Identifier: Apache-2.0
"""Controller for FundingRound endpoints (shared, no tenant/BU scoping)."""
import math
from typing import Annotated, Generator

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from common.controllers.base_controller_utils import create_service_dependency
from common.schemas.base_response_schema import PaginationLinks
from linkedout.funding.schemas.funding_round_api_schema import (
    CreateFundingRoundRequestSchema,
    CreateFundingRoundResponseSchema,
    DeleteFundingRoundByIdRequestSchema,
    GetFundingRoundByIdRequestSchema,
    GetFundingRoundByIdResponseSchema,
    ListFundingRoundsRequestSchema,
    ListFundingRoundsResponseSchema,
    UpdateFundingRoundRequestSchema,
    UpdateFundingRoundResponseSchema,
)
from linkedout.funding.services.funding_round_service import FundingRoundService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

funding_rounds_router = APIRouter(
    prefix='/funding-rounds',
    tags=['funding-rounds'],
)


def _get_service(request: Request) -> Generator[FundingRoundService, None, None]:
    yield from create_service_dependency(request, FundingRoundService, DbSessionType.READ)


def _get_write_service(request: Request) -> Generator[FundingRoundService, None, None]:
    yield from create_service_dependency(request, FundingRoundService, DbSessionType.WRITE)


@funding_rounds_router.get(
    '',
    response_model=ListFundingRoundsResponseSchema,
    summary='List funding rounds with filtering and pagination',
)
def list_funding_rounds(
    request: Request,
    list_request: Annotated[ListFundingRoundsRequestSchema, Query()],
    service: FundingRoundService = Depends(_get_service),
) -> ListFundingRoundsResponseSchema:
    funding_rounds, total = service.list_funding_rounds(list_request)
    page_count = math.ceil(total / list_request.limit) if total > 0 else 1
    return ListFundingRoundsResponseSchema(
        funding_rounds=funding_rounds,
        total=total,
        limit=list_request.limit,
        offset=list_request.offset,
        page_count=page_count,
    )


@funding_rounds_router.post(
    '',
    status_code=201,
    response_model=CreateFundingRoundResponseSchema,
    summary='Create a new funding round',
)
def create_funding_round(
    request: Request,
    create_request: Annotated[CreateFundingRoundRequestSchema, Body()],
    service: FundingRoundService = Depends(_get_write_service),
) -> CreateFundingRoundResponseSchema:
    created = service.create_funding_round(create_request)
    return CreateFundingRoundResponseSchema(funding_round=created)


@funding_rounds_router.patch(
    '/{funding_round_id}',
    response_model=UpdateFundingRoundResponseSchema,
    summary='Update a funding round',
)
def update_funding_round(
    request: Request,
    funding_round_id: str,
    update_request: Annotated[UpdateFundingRoundRequestSchema, Body()],
    service: FundingRoundService = Depends(_get_write_service),
) -> UpdateFundingRoundResponseSchema:
    update_request.funding_round_id = funding_round_id
    try:
        updated = service.update_funding_round(update_request)
        return UpdateFundingRoundResponseSchema(funding_round=updated)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@funding_rounds_router.get(
    '/{funding_round_id}',
    response_model=GetFundingRoundByIdResponseSchema,
    summary='Get a funding round by ID',
)
def get_funding_round_by_id(
    funding_round_id: str,
    service: FundingRoundService = Depends(_get_service),
) -> GetFundingRoundByIdResponseSchema:
    req = GetFundingRoundByIdRequestSchema(funding_round_id=funding_round_id)
    result = service.get_funding_round_by_id(req)
    if not result:
        raise HTTPException(status_code=404, detail=f'FundingRound {funding_round_id} not found')
    return GetFundingRoundByIdResponseSchema(funding_round=result)


@funding_rounds_router.delete(
    '/{funding_round_id}',
    status_code=204,
    summary='Delete a funding round',
)
def delete_funding_round_by_id(
    funding_round_id: str,
    service: FundingRoundService = Depends(_get_write_service),
) -> None:
    try:
        req = DeleteFundingRoundByIdRequestSchema(funding_round_id=funding_round_id)
        service.delete_funding_round_by_id(req)
        return Response(status_code=204)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
