# SPDX-License-Identifier: Apache-2.0
"""Controller for SearchSession endpoints using CRUDRouterFactory."""
from common.controllers.crud_router_factory import CRUDRouterConfig, create_crud_router
from linkedout.search_session.schemas.search_session_api_schema import (
    CreateSearchSessionRequestSchema,
    CreateSearchSessionResponseSchema,
    CreateSearchSessionsRequestSchema,
    CreateSearchSessionsResponseSchema,
    DeleteSearchSessionByIdRequestSchema,
    GetSearchSessionByIdRequestSchema,
    GetSearchSessionByIdResponseSchema,
    ListSearchSessionsRequestSchema,
    ListSearchSessionsResponseSchema,
    UpdateSearchSessionRequestSchema,
    UpdateSearchSessionResponseSchema,
)
from linkedout.search_session.services.search_session_service import SearchSessionService

_config = CRUDRouterConfig(
    prefix='/tenants/{tenant_id}/bus/{bu_id}/search-sessions',
    tags=['search-sessions'],
    service_class=SearchSessionService,
    entity_name='search_session',
    entity_name_plural='search_sessions',
    list_request_schema=ListSearchSessionsRequestSchema,
    list_response_schema=ListSearchSessionsResponseSchema,
    create_request_schema=CreateSearchSessionRequestSchema,
    create_response_schema=CreateSearchSessionResponseSchema,
    create_bulk_request_schema=CreateSearchSessionsRequestSchema,
    create_bulk_response_schema=CreateSearchSessionsResponseSchema,
    update_request_schema=UpdateSearchSessionRequestSchema,
    update_response_schema=UpdateSearchSessionResponseSchema,
    get_by_id_request_schema=GetSearchSessionByIdRequestSchema,
    get_by_id_response_schema=GetSearchSessionByIdResponseSchema,
    delete_by_id_request_schema=DeleteSearchSessionByIdRequestSchema,
    meta_fields=['sort_by', 'sort_order', 'app_user_id', 'is_saved'],
)

_result = create_crud_router(_config)
search_sessions_router = _result.router
_get_search_session_service = _result.get_service
_get_write_search_session_service = _result.get_write_service
