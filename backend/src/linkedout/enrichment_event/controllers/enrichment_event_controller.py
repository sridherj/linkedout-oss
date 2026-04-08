# SPDX-License-Identifier: Apache-2.0
"""Controller for EnrichmentEvent endpoints (scoped to tenant/BU)."""
import math
from typing import Annotated, Generator

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from common.controllers.base_controller_utils import build_pagination_links, create_service_dependency
from linkedout.enrichment_event.schemas.enrichment_event_api_schema import (
    CreateEnrichmentEventRequestSchema,
    CreateEnrichmentEventResponseSchema,
    CreateEnrichmentEventsRequestSchema,
    CreateEnrichmentEventsResponseSchema,
    DeleteEnrichmentEventByIdRequestSchema,
    GetEnrichmentEventByIdRequestSchema,
    GetEnrichmentEventByIdResponseSchema,
    ListEnrichmentEventsRequestSchema,
    ListEnrichmentEventsResponseSchema,
    UpdateEnrichmentEventRequestSchema,
    UpdateEnrichmentEventResponseSchema,
)
from linkedout.enrichment_event.services.enrichment_event_service import EnrichmentEventService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

enrichment_events_router = APIRouter(
    prefix='/tenants/{tenant_id}/bus/{bu_id}/enrichment-events',
    tags=['enrichment-events'],
)

_META_FIELDS = [
    'sort_by', 'sort_order', 'app_user_id', 'crawled_profile_id',
    'event_type', 'enrichment_mode',
]


def _get_enrichment_event_service() -> Generator[EnrichmentEventService, None, None]:
    yield from create_service_dependency(EnrichmentEventService, DbSessionType.READ)


def _get_write_enrichment_event_service() -> Generator[EnrichmentEventService, None, None]:
    yield from create_service_dependency(EnrichmentEventService, DbSessionType.WRITE)


@enrichment_events_router.get(
    '', response_model=ListEnrichmentEventsResponseSchema,
    summary='List enrichment events with filtering and pagination',
)
def list_enrichment_events(
    request: Request, tenant_id: str, bu_id: str,
    list_request: Annotated[ListEnrichmentEventsRequestSchema, Query()],
    service: EnrichmentEventService = Depends(_get_enrichment_event_service),
):
    list_request.tenant_id = tenant_id
    list_request.bu_id = bu_id

    try:
        enrichment_events, total_count = service.list_entities(list_request)
        meta = {field: getattr(list_request, field, None) for field in _META_FIELDS}

        if total_count > 0:
            page_count = math.ceil(total_count / list_request.limit)
            links = build_pagination_links(
                request=request, entity_path='enrichment-events',
                tenant_id=tenant_id, bu_id=bu_id,
                total=total_count, limit=list_request.limit, offset=list_request.offset,
                params=meta,
            )
            return ListEnrichmentEventsResponseSchema(
                enrichment_events=enrichment_events, total=total_count,
                limit=list_request.limit, offset=list_request.offset,
                page_count=page_count, links=links, meta=meta,
            )
        else:
            return ListEnrichmentEventsResponseSchema(
                enrichment_events=[], total=0,
                limit=list_request.limit, offset=list_request.offset,
                page_count=1, links=None, meta=meta,
            )
    except Exception as e:
        logger.error(f'Error listing enrichment events: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to list enrichment events: {str(e)}')


@enrichment_events_router.post(
    '', status_code=201,
    response_model=CreateEnrichmentEventResponseSchema,
    summary='Create a new enrichment event',
)
def create_enrichment_event(
    tenant_id: str, bu_id: str,
    create_request: Annotated[CreateEnrichmentEventRequestSchema, Body()],
    service: EnrichmentEventService = Depends(_get_write_enrichment_event_service),
):
    create_request.tenant_id = tenant_id
    create_request.bu_id = bu_id
    try:
        created = service.create_entity(create_request)
        return CreateEnrichmentEventResponseSchema(enrichment_event=created)
    except Exception as e:
        logger.error(f'Error creating enrichment event: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create enrichment event: {str(e)}')


@enrichment_events_router.post(
    '/bulk', status_code=201,
    response_model=CreateEnrichmentEventsResponseSchema,
    summary='Create multiple enrichment events',
)
def create_enrichment_events_bulk(
    tenant_id: str, bu_id: str,
    create_request: Annotated[CreateEnrichmentEventsRequestSchema, Body()],
    service: EnrichmentEventService = Depends(_get_write_enrichment_event_service),
):
    create_request.tenant_id = tenant_id
    create_request.bu_id = bu_id
    try:
        created = service.create_entities_bulk(create_request)
        return CreateEnrichmentEventsResponseSchema(enrichment_events=created)
    except Exception as e:
        logger.error(f'Error creating enrichment events: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create enrichment events: {str(e)}')


@enrichment_events_router.patch(
    '/{enrichment_event_id}',
    response_model=UpdateEnrichmentEventResponseSchema,
    summary='Update an enrichment event',
)
def update_enrichment_event(
    tenant_id: str, bu_id: str, enrichment_event_id: str,
    update_request: Annotated[UpdateEnrichmentEventRequestSchema, Body()],
    service: EnrichmentEventService = Depends(_get_write_enrichment_event_service),
):
    update_request.tenant_id = tenant_id
    update_request.bu_id = bu_id
    update_request.enrichment_event_id = enrichment_event_id
    try:
        updated = service.update_entity(update_request)
        return UpdateEnrichmentEventResponseSchema(enrichment_event=updated)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error updating enrichment event: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to update enrichment event: {str(e)}')


@enrichment_events_router.get(
    '/{enrichment_event_id}',
    response_model=GetEnrichmentEventByIdResponseSchema,
    summary='Get an enrichment event by ID',
)
def get_enrichment_event_by_id(
    tenant_id: str, bu_id: str, enrichment_event_id: str,
    service: EnrichmentEventService = Depends(_get_enrichment_event_service),
):
    get_request = GetEnrichmentEventByIdRequestSchema(
        tenant_id=tenant_id, bu_id=bu_id, enrichment_event_id=enrichment_event_id
    )
    try:
        enrichment_event = service.get_entity_by_id(get_request)
        if not enrichment_event:
            raise HTTPException(status_code=404, detail=f'EnrichmentEvent with ID {enrichment_event_id} not found')
        return GetEnrichmentEventByIdResponseSchema(enrichment_event=enrichment_event)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting enrichment event {enrichment_event_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to get enrichment event: {str(e)}')


@enrichment_events_router.delete(
    '/{enrichment_event_id}', status_code=204,
    summary='Delete an enrichment event by ID',
)
def delete_enrichment_event_by_id(
    tenant_id: str, bu_id: str, enrichment_event_id: str,
    service: EnrichmentEventService = Depends(_get_write_enrichment_event_service),
):
    delete_request = DeleteEnrichmentEventByIdRequestSchema(
        tenant_id=tenant_id, bu_id=bu_id, enrichment_event_id=enrichment_event_id
    )
    try:
        service.delete_entity_by_id(delete_request)
        return Response(status_code=204)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error deleting enrichment event {enrichment_event_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to delete enrichment event: {str(e)}')
