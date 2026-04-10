# SPDX-License-Identifier: Apache-2.0
"""Controller for ContactSource endpoints (scoped to tenant/BU)."""
import math
from typing import Annotated, Generator

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from common.controllers.base_controller_utils import build_pagination_links, create_service_dependency
from linkedout.contact_source.schemas.contact_source_api_schema import (
    CreateContactSourceRequestSchema,
    CreateContactSourceResponseSchema,
    CreateContactSourcesRequestSchema,
    CreateContactSourcesResponseSchema,
    DeleteContactSourceByIdRequestSchema,
    GetContactSourceByIdRequestSchema,
    GetContactSourceByIdResponseSchema,
    ListContactSourcesRequestSchema,
    ListContactSourcesResponseSchema,
    UpdateContactSourceRequestSchema,
    UpdateContactSourceResponseSchema,
)
from linkedout.contact_source.services.contact_source_service import ContactSourceService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

contact_sources_router = APIRouter(
    prefix='/tenants/{tenant_id}/bus/{bu_id}/contact-sources',
    tags=['contact-sources'],
)

_META_FIELDS = [
    'sort_by', 'sort_order', 'app_user_id', 'import_job_id',
    'source_type', 'dedup_status', 'connection_id',
]


def _get_contact_source_service(request: Request) -> Generator[ContactSourceService, None, None]:
    yield from create_service_dependency(request, ContactSourceService, DbSessionType.READ)


def _get_write_contact_source_service(request: Request) -> Generator[ContactSourceService, None, None]:
    yield from create_service_dependency(request, ContactSourceService, DbSessionType.WRITE)


@contact_sources_router.get(
    '', response_model=ListContactSourcesResponseSchema,
    summary='List contact sources with filtering and pagination',
)
def list_contact_sources(
    request: Request, tenant_id: str, bu_id: str,
    list_request: Annotated[ListContactSourcesRequestSchema, Query()],
    service: ContactSourceService = Depends(_get_contact_source_service),
):
    list_request.tenant_id = tenant_id
    list_request.bu_id = bu_id

    try:
        contact_sources, total_count = service.list_entities(list_request)
        meta = {field: getattr(list_request, field, None) for field in _META_FIELDS}

        if total_count > 0:
            page_count = math.ceil(total_count / list_request.limit)
            links = build_pagination_links(
                request=request, entity_path='contact-sources',
                tenant_id=tenant_id, bu_id=bu_id,
                total=total_count, limit=list_request.limit, offset=list_request.offset,
                params=meta,
            )
            return ListContactSourcesResponseSchema(
                contact_sources=contact_sources, total=total_count,
                limit=list_request.limit, offset=list_request.offset,
                page_count=page_count, links=links, meta=meta,
            )
        else:
            return ListContactSourcesResponseSchema(
                contact_sources=[], total=0,
                limit=list_request.limit, offset=list_request.offset,
                page_count=1, links=None, meta=meta,
            )
    except Exception as e:
        logger.error(f'Error listing contact sources: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to list contact sources: {str(e)}')


@contact_sources_router.post(
    '', status_code=201,
    response_model=CreateContactSourceResponseSchema,
    summary='Create a new contact source',
)
def create_contact_source(
    tenant_id: str, bu_id: str,
    create_request: Annotated[CreateContactSourceRequestSchema, Body()],
    service: ContactSourceService = Depends(_get_write_contact_source_service),
):
    create_request.tenant_id = tenant_id
    create_request.bu_id = bu_id
    try:
        created = service.create_entity(create_request)
        return CreateContactSourceResponseSchema(contact_source=created)
    except Exception as e:
        logger.error(f'Error creating contact source: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create contact source: {str(e)}')


@contact_sources_router.post(
    '/bulk', status_code=201,
    response_model=CreateContactSourcesResponseSchema,
    summary='Create multiple contact sources',
)
def create_contact_sources_bulk(
    tenant_id: str, bu_id: str,
    create_request: Annotated[CreateContactSourcesRequestSchema, Body()],
    service: ContactSourceService = Depends(_get_write_contact_source_service),
):
    create_request.tenant_id = tenant_id
    create_request.bu_id = bu_id
    try:
        created = service.create_entities_bulk(create_request)
        return CreateContactSourcesResponseSchema(contact_sources=created)
    except Exception as e:
        logger.error(f'Error creating contact sources: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create contact sources: {str(e)}')


@contact_sources_router.patch(
    '/{contact_source_id}',
    response_model=UpdateContactSourceResponseSchema,
    summary='Update a contact source',
)
def update_contact_source(
    tenant_id: str, bu_id: str, contact_source_id: str,
    update_request: Annotated[UpdateContactSourceRequestSchema, Body()],
    service: ContactSourceService = Depends(_get_write_contact_source_service),
):
    update_request.tenant_id = tenant_id
    update_request.bu_id = bu_id
    update_request.contact_source_id = contact_source_id
    try:
        updated = service.update_entity(update_request)
        return UpdateContactSourceResponseSchema(contact_source=updated)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error updating contact source: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to update contact source: {str(e)}')


@contact_sources_router.get(
    '/{contact_source_id}',
    response_model=GetContactSourceByIdResponseSchema,
    summary='Get a contact source by ID',
)
def get_contact_source_by_id(
    tenant_id: str, bu_id: str, contact_source_id: str,
    service: ContactSourceService = Depends(_get_contact_source_service),
):
    get_request = GetContactSourceByIdRequestSchema(
        tenant_id=tenant_id, bu_id=bu_id, contact_source_id=contact_source_id
    )
    try:
        contact_source = service.get_entity_by_id(get_request)
        if not contact_source:
            raise HTTPException(status_code=404, detail=f'Contact source with ID {contact_source_id} not found')
        return GetContactSourceByIdResponseSchema(contact_source=contact_source)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting contact source {contact_source_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to get contact source: {str(e)}')


@contact_sources_router.delete(
    '/{contact_source_id}', status_code=204,
    summary='Delete a contact source by ID',
)
def delete_contact_source_by_id(
    tenant_id: str, bu_id: str, contact_source_id: str,
    service: ContactSourceService = Depends(_get_write_contact_source_service),
):
    delete_request = DeleteContactSourceByIdRequestSchema(
        tenant_id=tenant_id, bu_id=bu_id, contact_source_id=contact_source_id
    )
    try:
        service.delete_entity_by_id(delete_request)
        return Response(status_code=204)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error deleting contact source {contact_source_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to delete contact source: {str(e)}')
