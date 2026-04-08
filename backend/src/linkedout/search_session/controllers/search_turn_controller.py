# SPDX-License-Identifier: Apache-2.0
"""Controller for SearchTurn endpoints — CRUD at flat URL + nested listing."""
from typing import Generator

from fastapi import Depends, Query

from common.controllers.base_controller_utils import create_service_dependency
from common.controllers.crud_router_factory import CRUDRouterConfig, create_crud_router
from linkedout.search_session.schemas.search_turn_api_schema import (
    CreateSearchTurnRequestSchema,
    CreateSearchTurnResponseSchema,
    CreateSearchTurnsRequestSchema,
    CreateSearchTurnsResponseSchema,
    DeleteSearchTurnByIdRequestSchema,
    GetSearchTurnByIdRequestSchema,
    GetSearchTurnByIdResponseSchema,
    ListSearchTurnsRequestSchema,
    ListSearchTurnsResponseSchema,
    UpdateSearchTurnRequestSchema,
    UpdateSearchTurnResponseSchema,
)
from linkedout.search_session.services.search_turn_service import SearchTurnService
from shared.infra.db.db_session_manager import DbSessionType

# Standard CRUD at flat URL
_config = CRUDRouterConfig(
    prefix='/tenants/{tenant_id}/bus/{bu_id}/search-turns',
    tags=['search-turns'],
    service_class=SearchTurnService,
    entity_name='search_turn',
    entity_name_plural='search_turns',
    list_request_schema=ListSearchTurnsRequestSchema,
    list_response_schema=ListSearchTurnsResponseSchema,
    create_request_schema=CreateSearchTurnRequestSchema,
    create_response_schema=CreateSearchTurnResponseSchema,
    create_bulk_request_schema=CreateSearchTurnsRequestSchema,
    create_bulk_response_schema=CreateSearchTurnsResponseSchema,
    update_request_schema=UpdateSearchTurnRequestSchema,
    update_response_schema=UpdateSearchTurnResponseSchema,
    get_by_id_request_schema=GetSearchTurnByIdRequestSchema,
    get_by_id_response_schema=GetSearchTurnByIdResponseSchema,
    delete_by_id_request_schema=DeleteSearchTurnByIdRequestSchema,
    meta_fields=['sort_by', 'sort_order', 'session_id'],
)

_result = create_crud_router(_config)
search_turns_router = _result.router
_get_search_turn_service = _result.get_service
_get_write_search_turn_service = _result.get_write_service


# -- Nested listing: GET /tenants/{tenant_id}/bus/{bu_id}/search-sessions/{session_id}/turns --

def _get_read_service() -> Generator[SearchTurnService, None, None]:
    yield from create_service_dependency(SearchTurnService, DbSessionType.READ)


@search_turns_router.get(
    '/by-session/{session_id}',
    response_model=ListSearchTurnsResponseSchema,
    tags=['search-turns'],
    summary='List turns for a specific session',
)
async def list_turns_by_session(
    tenant_id: str,
    bu_id: str,
    session_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: SearchTurnService = Depends(_get_read_service),
) -> ListSearchTurnsResponseSchema:
    """List turns for a session ordered by turn_number ASC."""
    list_request = ListSearchTurnsRequestSchema(
        tenant_id=tenant_id,
        bu_id=bu_id,
        session_id=session_id,
        limit=limit,
        offset=offset,
    )
    items, total_count = service.list_entities(list_request)
    return ListSearchTurnsResponseSchema(
        search_turns=items,
        total=total_count,
        limit=limit,
        offset=offset,
        page_count=max(1, -(-total_count // limit)),
    )
