# SPDX-License-Identifier: Apache-2.0
"""Controller for Connection endpoints (scoped to tenant/BU)."""
import math
from typing import Annotated, Generator

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, Response
from psycopg2.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError

from common.controllers.base_controller_utils import build_pagination_links, create_service_dependency
from linkedout.connection.schemas.connection_api_schema import (
    CreateConnectionRequestSchema,
    CreateConnectionResponseSchema,
    CreateConnectionsRequestSchema,
    CreateConnectionsResponseSchema,
    DeleteConnectionByIdRequestSchema,
    GetConnectionByIdRequestSchema,
    GetConnectionByIdResponseSchema,
    ListConnectionsRequestSchema,
    ListConnectionsResponseSchema,
    UpdateConnectionRequestSchema,
    UpdateConnectionResponseSchema,
)
from linkedout.connection.services.connection_service import ConnectionService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

connections_router = APIRouter(
    prefix='/tenants/{tenant_id}/bus/{bu_id}/connections',
    tags=['connections'],
)

_META_FIELDS = [
    'sort_by', 'sort_order', 'app_user_id', 'crawled_profile_id',
    'dunbar_tier', 'affinity_score_min', 'affinity_score_max',
]


def _get_connection_service(
    app_user_id: str = Header(..., alias="X-App-User-Id"),
) -> Generator[ConnectionService, None, None]:
    yield from create_service_dependency(ConnectionService, DbSessionType.READ, app_user_id=app_user_id)


def _get_write_connection_service() -> Generator[ConnectionService, None, None]:
    yield from create_service_dependency(ConnectionService, DbSessionType.WRITE)


@connections_router.get(
    '', response_model=ListConnectionsResponseSchema,
    summary='List connections with filtering and pagination',
)
def list_connections(
    request: Request, tenant_id: str, bu_id: str,
    list_request: Annotated[ListConnectionsRequestSchema, Query()],
    service: ConnectionService = Depends(_get_connection_service),
):
    list_request.tenant_id = tenant_id
    list_request.bu_id = bu_id

    try:
        connections, total_count = service.list_entities(list_request)
        meta = {field: getattr(list_request, field, None) for field in _META_FIELDS}

        if total_count > 0:
            page_count = math.ceil(total_count / list_request.limit)
            links = build_pagination_links(
                request=request, entity_path='connections',
                tenant_id=tenant_id, bu_id=bu_id,
                total=total_count, limit=list_request.limit, offset=list_request.offset,
                params=meta,
            )
            return ListConnectionsResponseSchema(
                connections=connections, total=total_count,
                limit=list_request.limit, offset=list_request.offset,
                page_count=page_count, links=links, meta=meta,
            )
        else:
            return ListConnectionsResponseSchema(
                connections=[], total=0,
                limit=list_request.limit, offset=list_request.offset,
                page_count=1, links=None, meta=meta,
            )
    except Exception as e:
        logger.error(f'Error listing connections: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to list connections: {str(e)}')


@connections_router.post(
    '', status_code=201,
    response_model=CreateConnectionResponseSchema,
    summary='Create a new connection',
)
def create_connection(
    tenant_id: str, bu_id: str,
    create_request: Annotated[CreateConnectionRequestSchema, Body()],
    service: ConnectionService = Depends(_get_write_connection_service),
):
    create_request.tenant_id = tenant_id
    create_request.bu_id = bu_id
    try:
        created = service.create_entity(create_request)
        return CreateConnectionResponseSchema(connection=created)
    except IntegrityError as e:
        if isinstance(e.orig, UniqueViolation):
            raise HTTPException(status_code=409, detail='Connection already exists for this user and profile')
        logger.error(f'Error creating connection: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create connection: {str(e)}')
    except Exception as e:
        logger.error(f'Error creating connection: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create connection: {str(e)}')


@connections_router.post(
    '/bulk', status_code=201,
    response_model=CreateConnectionsResponseSchema,
    summary='Create multiple connections',
)
def create_connections_bulk(
    tenant_id: str, bu_id: str,
    create_request: Annotated[CreateConnectionsRequestSchema, Body()],
    service: ConnectionService = Depends(_get_write_connection_service),
):
    create_request.tenant_id = tenant_id
    create_request.bu_id = bu_id
    try:
        created = service.create_entities_bulk(create_request)
        return CreateConnectionsResponseSchema(connections=created)
    except Exception as e:
        logger.error(f'Error creating connections: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create connections: {str(e)}')


@connections_router.patch(
    '/{connection_id}',
    response_model=UpdateConnectionResponseSchema,
    summary='Update a connection',
)
def update_connection(
    tenant_id: str, bu_id: str, connection_id: str,
    update_request: Annotated[UpdateConnectionRequestSchema, Body()],
    service: ConnectionService = Depends(_get_write_connection_service),
):
    update_request.tenant_id = tenant_id
    update_request.bu_id = bu_id
    update_request.connection_id = connection_id
    try:
        updated = service.update_entity(update_request)
        return UpdateConnectionResponseSchema(connection=updated)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error updating connection: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to update connection: {str(e)}')


@connections_router.get(
    '/{connection_id}',
    response_model=GetConnectionByIdResponseSchema,
    summary='Get a connection by ID',
)
def get_connection_by_id(
    tenant_id: str, bu_id: str, connection_id: str,
    service: ConnectionService = Depends(_get_connection_service),
):
    get_request = GetConnectionByIdRequestSchema(
        tenant_id=tenant_id, bu_id=bu_id, connection_id=connection_id
    )
    try:
        connection = service.get_entity_by_id(get_request)
        if not connection:
            raise HTTPException(status_code=404, detail=f'Connection with ID {connection_id} not found')
        return GetConnectionByIdResponseSchema(connection=connection)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting connection {connection_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to get connection: {str(e)}')


@connections_router.delete(
    '/{connection_id}', status_code=204,
    summary='Delete a connection by ID',
)
def delete_connection_by_id(
    tenant_id: str, bu_id: str, connection_id: str,
    service: ConnectionService = Depends(_get_write_connection_service),
):
    delete_request = DeleteConnectionByIdRequestSchema(
        tenant_id=tenant_id, bu_id=bu_id, connection_id=connection_id
    )
    try:
        service.delete_entity_by_id(delete_request)
        return Response(status_code=204)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error deleting connection {connection_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to delete connection: {str(e)}')
