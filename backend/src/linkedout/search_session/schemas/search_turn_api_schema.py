# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for SearchTurn API."""
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.search_session.schemas.search_turn_schema import SearchTurnSchema


class SearchTurnSortByFields(StrEnum):
    TURN_NUMBER = 'turn_number'
    CREATED_AT = 'created_at'


class ListSearchTurnsRequestSchema(PaginateRequestSchema):
    tenant_id: Annotated[Optional[str], Field(description='Tenant ID filter', default=None)] = None
    bu_id: Annotated[Optional[str], Field(description='Business Unit ID filter', default=None)] = None
    sort_by: Annotated[SearchTurnSortByFields, Field(description='Sort field', default=SearchTurnSortByFields.TURN_NUMBER)] = SearchTurnSortByFields.TURN_NUMBER
    sort_order: Annotated[SortOrder, Field(description='Sort order', default=SortOrder.ASC)] = SortOrder.ASC
    session_id: Annotated[Optional[str], Field(description='Filter by session ID', default=None)] = None


class CreateSearchTurnRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(description='Tenant ID', default=None)] = None
    bu_id: Annotated[Optional[str], Field(description='Business Unit ID', default=None)] = None
    session_id: Annotated[str, Field(description='Parent search session ID')]
    turn_number: Annotated[int, Field(description='1-indexed turn number')]
    user_query: Annotated[str, Field(description='User query for this turn')]
    transcript: Annotated[Optional[dict], Field(description='Full LLM messages array', default=None)] = None
    results: Annotated[Optional[list], Field(description='Structured result set', default=None)] = None
    summary: Annotated[Optional[str], Field(description='LLM-generated summary', default=None)] = None


class CreateSearchTurnsRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    search_turns: List[CreateSearchTurnRequestSchema]


class UpdateSearchTurnRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(description='Tenant ID', default=None)] = None
    bu_id: Annotated[Optional[str], Field(description='Business Unit ID', default=None)] = None
    search_turn_id: Annotated[Optional[str], Field(description='Search turn ID to update', default=None)] = None
    transcript: Annotated[Optional[dict], Field(description='Full LLM messages array', default=None)] = None
    results: Annotated[Optional[list], Field(description='Structured result set', default=None)] = None
    summary: Annotated[Optional[str], Field(description='LLM-generated summary', default=None)] = None


class GetSearchTurnByIdRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    search_turn_id: Optional[str] = None


class DeleteSearchTurnByIdRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    search_turn_id: Optional[str] = None


class ListSearchTurnsResponseSchema(PaginateResponseSchema):
    search_turns: List[SearchTurnSchema]


class CreateSearchTurnResponseSchema(BaseResponseSchema):
    search_turn: SearchTurnSchema


class CreateSearchTurnsResponseSchema(BaseResponseSchema):
    search_turns: List[SearchTurnSchema]


class UpdateSearchTurnResponseSchema(BaseResponseSchema):
    search_turn: SearchTurnSchema


class GetSearchTurnByIdResponseSchema(BaseResponseSchema):
    search_turn: SearchTurnSchema
