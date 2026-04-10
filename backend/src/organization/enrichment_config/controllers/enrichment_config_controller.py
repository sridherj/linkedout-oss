# SPDX-License-Identifier: Apache-2.0
"""Controller for EnrichmentConfig endpoints."""
from typing import Annotated, Generator

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from organization.enrichment_config.schemas.enrichment_config_api_schema import (
    CreateEnrichmentConfigRequestSchema,
    CreateEnrichmentConfigResponseSchema,
    GetEnrichmentConfigByIdResponseSchema,
    ListEnrichmentConfigsRequestSchema,
    ListEnrichmentConfigsResponseSchema,
    UpdateEnrichmentConfigRequestSchema,
    UpdateEnrichmentConfigResponseSchema,
)
from organization.enrichment_config.services.enrichment_config_service import EnrichmentConfigService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

enrichment_configs_router = APIRouter(
    prefix='/enrichment-configs',
    tags=['enrichment-configs'],
)


def _get_service(
    request: Request,
    session_type: DbSessionType = DbSessionType.READ,
) -> Generator[EnrichmentConfigService, None, None]:
    db_manager = request.app.state.db_manager
    with db_manager.get_session(session_type) as session:
        yield EnrichmentConfigService(session)


def _get_write_service(request: Request) -> Generator[EnrichmentConfigService, None, None]:
    yield from _get_service(request, session_type=DbSessionType.WRITE)


@enrichment_configs_router.get(
    '',
    response_model=ListEnrichmentConfigsResponseSchema,
    summary='List enrichment configs with filtering and pagination',
)
def list_enrichment_configs(
    list_request: Annotated[ListEnrichmentConfigsRequestSchema, Query()],
    service: EnrichmentConfigService = Depends(_get_service),
) -> ListEnrichmentConfigsResponseSchema:
    try:
        items, total_count = service.list_enrichment_configs(list_request)
        return ListEnrichmentConfigsResponseSchema(
            enrichment_configs=items,
            total=total_count,
            limit=list_request.limit,
            offset=list_request.offset,
            page_count=max(1, -(-total_count // list_request.limit)),
            links=None,
            meta={},
        )
    except Exception as e:
        logger.error(f'Error listing enrichment configs: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to list enrichment configs: {str(e)}')


@enrichment_configs_router.post(
    '',
    status_code=201,
    response_model=CreateEnrichmentConfigResponseSchema,
    summary='Create an enrichment config',
)
def create_enrichment_config(
    create_request: Annotated[CreateEnrichmentConfigRequestSchema, Body()],
    service: EnrichmentConfigService = Depends(_get_write_service),
) -> CreateEnrichmentConfigResponseSchema:
    try:
        created = service.create_enrichment_config(create_request)
        return CreateEnrichmentConfigResponseSchema(enrichment_config=created)
    except Exception as e:
        logger.error(f'Error creating enrichment config: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create enrichment config: {str(e)}')


@enrichment_configs_router.get(
    '/{enrichment_config_id}',
    response_model=GetEnrichmentConfigByIdResponseSchema,
    summary='Get an enrichment config by ID',
)
def get_enrichment_config_by_id(
    enrichment_config_id: str,
    service: EnrichmentConfigService = Depends(_get_service),
) -> GetEnrichmentConfigByIdResponseSchema:
    item = service.get_enrichment_config_by_id(enrichment_config_id)
    if not item:
        raise HTTPException(status_code=404, detail=f'EnrichmentConfig with ID {enrichment_config_id} not found')
    return GetEnrichmentConfigByIdResponseSchema(enrichment_config=item)


@enrichment_configs_router.patch(
    '/{enrichment_config_id}',
    response_model=UpdateEnrichmentConfigResponseSchema,
    summary='Update an enrichment config',
)
def update_enrichment_config(
    enrichment_config_id: str,
    update_request: Annotated[UpdateEnrichmentConfigRequestSchema, Body()],
    service: EnrichmentConfigService = Depends(_get_write_service),
) -> UpdateEnrichmentConfigResponseSchema:
    try:
        updated = service.update_enrichment_config(enrichment_config_id, update_request)
        return UpdateEnrichmentConfigResponseSchema(enrichment_config=updated)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error updating enrichment config: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to update enrichment config: {str(e)}')


@enrichment_configs_router.delete(
    '/{enrichment_config_id}',
    status_code=204,
    summary='Delete an enrichment config',
)
def delete_enrichment_config(
    enrichment_config_id: str,
    service: EnrichmentConfigService = Depends(_get_write_service),
):
    try:
        service.delete_enrichment_config_by_id(enrichment_config_id)
        return Response(status_code=204)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error deleting enrichment config: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to delete enrichment config: {str(e)}')
