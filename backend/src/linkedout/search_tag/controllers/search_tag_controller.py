# SPDX-License-Identifier: Apache-2.0
"""Controller for SearchTag endpoints using CRUDRouterFactory."""
from common.controllers.crud_router_factory import CRUDRouterConfig, create_crud_router
from linkedout.search_tag.schemas.search_tag_api_schema import (
    CreateSearchTagRequestSchema,
    CreateSearchTagResponseSchema,
    CreateSearchTagsRequestSchema,
    CreateSearchTagsResponseSchema,
    DeleteSearchTagByIdRequestSchema,
    GetSearchTagByIdRequestSchema,
    GetSearchTagByIdResponseSchema,
    ListSearchTagsRequestSchema,
    ListSearchTagsResponseSchema,
    UpdateSearchTagRequestSchema,
    UpdateSearchTagResponseSchema,
)
from linkedout.search_tag.services.search_tag_service import SearchTagService

_config = CRUDRouterConfig(
    prefix='/tenants/{tenant_id}/bus/{bu_id}/search-tags',
    tags=['search-tags'],
    service_class=SearchTagService,
    entity_name='search_tag',
    entity_name_plural='search_tags',
    list_request_schema=ListSearchTagsRequestSchema,
    list_response_schema=ListSearchTagsResponseSchema,
    create_request_schema=CreateSearchTagRequestSchema,
    create_response_schema=CreateSearchTagResponseSchema,
    create_bulk_request_schema=CreateSearchTagsRequestSchema,
    create_bulk_response_schema=CreateSearchTagsResponseSchema,
    update_request_schema=UpdateSearchTagRequestSchema,
    update_response_schema=UpdateSearchTagResponseSchema,
    get_by_id_request_schema=GetSearchTagByIdRequestSchema,
    get_by_id_response_schema=GetSearchTagByIdResponseSchema,
    delete_by_id_request_schema=DeleteSearchTagByIdRequestSchema,
    meta_fields=['sort_by', 'sort_order', 'app_user_id', 'session_id', 'crawled_profile_id', 'tag_name'],
)

_result = create_crud_router(_config)
search_tags_router = _result.router
_get_search_tag_service = _result.get_service
_get_write_search_tag_service = _result.get_write_service
