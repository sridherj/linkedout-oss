# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for SearchSession API."""
from datetime import datetime
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.search_session.schemas.search_session_schema import SearchSessionSchema


class SearchSessionSortByFields(StrEnum):
    LAST_ACTIVE_AT = 'last_active_at'
    CREATED_AT = 'created_at'
    TURN_COUNT = 'turn_count'


class ListSearchSessionsRequestSchema(PaginateRequestSchema):
    tenant_id: Annotated[Optional[str], Field(description='Tenant ID filter', default=None)] = None
    bu_id: Annotated[Optional[str], Field(description='Business Unit ID filter', default=None)] = None
    sort_by: Annotated[SearchSessionSortByFields, Field(description='Sort field', default=SearchSessionSortByFields.LAST_ACTIVE_AT)] = SearchSessionSortByFields.LAST_ACTIVE_AT
    sort_order: Annotated[SortOrder, Field(description='Sort order', default=SortOrder.DESC)] = SortOrder.DESC
    app_user_id: Annotated[Optional[str], Field(description='Filter by user ID', default=None)] = None
    is_saved: Annotated[Optional[bool], Field(description='Filter by saved status', default=None)] = None


class CreateSearchSessionRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(description='Tenant ID', default=None)] = None
    bu_id: Annotated[Optional[str], Field(description='Business Unit ID', default=None)] = None
    app_user_id: Annotated[str, Field(description='User who owns the session')]
    initial_query: Annotated[str, Field(description='First search query')]
    turn_count: Annotated[int, Field(description='Number of conversation turns', default=1)] = 1
    last_active_at: Annotated[Optional[datetime], Field(description='Last activity timestamp', default=None)] = None


class CreateSearchSessionsRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    search_sessions: List[CreateSearchSessionRequestSchema]


class UpdateSearchSessionRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(description='Tenant ID', default=None)] = None
    bu_id: Annotated[Optional[str], Field(description='Business Unit ID', default=None)] = None
    search_session_id: Annotated[Optional[str], Field(description='Search session ID to update', default=None)] = None
    initial_query: Annotated[Optional[str], Field(description='First search query', default=None)] = None
    turn_count: Annotated[Optional[int], Field(description='Number of conversation turns', default=None)] = None
    last_active_at: Annotated[Optional[datetime], Field(description='Last activity timestamp', default=None)] = None
    is_saved: Annotated[Optional[bool], Field(description='Whether this session is saved/bookmarked', default=None)] = None
    saved_name: Annotated[Optional[str], Field(description='User-provided name for the saved session', default=None)] = None


class GetSearchSessionByIdRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    search_session_id: Optional[str] = None


class DeleteSearchSessionByIdRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    search_session_id: Optional[str] = None


class ListSearchSessionsResponseSchema(PaginateResponseSchema):
    search_sessions: List[SearchSessionSchema]


class CreateSearchSessionResponseSchema(BaseResponseSchema):
    search_session: SearchSessionSchema


class CreateSearchSessionsResponseSchema(BaseResponseSchema):
    search_sessions: List[SearchSessionSchema]


class UpdateSearchSessionResponseSchema(BaseResponseSchema):
    search_session: SearchSessionSchema


class GetSearchSessionByIdResponseSchema(BaseResponseSchema):
    search_session: SearchSessionSchema
