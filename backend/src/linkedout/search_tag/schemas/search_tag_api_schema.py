# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for SearchTag API."""
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.search_tag.schemas.search_tag_schema import SearchTagSchema


class SearchTagSortByFields(StrEnum):
    CREATED_AT = 'created_at'
    TAG_NAME = 'tag_name'


class ListSearchTagsRequestSchema(PaginateRequestSchema):
    tenant_id: Annotated[Optional[str], Field(description='Tenant ID filter', default=None)] = None
    bu_id: Annotated[Optional[str], Field(description='Business Unit ID filter', default=None)] = None
    sort_by: Annotated[SearchTagSortByFields, Field(description='Sort field', default=SearchTagSortByFields.CREATED_AT)] = SearchTagSortByFields.CREATED_AT
    sort_order: Annotated[SortOrder, Field(description='Sort order', default=SortOrder.DESC)] = SortOrder.DESC
    app_user_id: Annotated[Optional[str], Field(description='Filter by user ID', default=None)] = None
    session_id: Annotated[Optional[str], Field(description='Filter by search session', default=None)] = None
    crawled_profile_id: Annotated[Optional[str], Field(description='Filter by tagged profile', default=None)] = None
    tag_name: Annotated[Optional[str], Field(description='Filter by tag name (ilike)', default=None)] = None


class CreateSearchTagRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(description='Tenant ID', default=None)] = None
    bu_id: Annotated[Optional[str], Field(description='Business Unit ID', default=None)] = None
    app_user_id: Annotated[str, Field(description='User who created the tag')]
    session_id: Annotated[str, Field(description='Search session where the tag was created')]
    crawled_profile_id: Annotated[str, Field(description='Tagged profile')]
    tag_name: Annotated[str, Field(description='Tag label')]


class CreateSearchTagsRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    search_tags: List[CreateSearchTagRequestSchema]


class UpdateSearchTagRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(description='Tenant ID', default=None)] = None
    bu_id: Annotated[Optional[str], Field(description='Business Unit ID', default=None)] = None
    search_tag_id: Annotated[Optional[str], Field(description='Search tag ID to update', default=None)] = None
    tag_name: Annotated[Optional[str], Field(description='Tag label', default=None)] = None


class GetSearchTagByIdRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    search_tag_id: Optional[str] = None


class DeleteSearchTagByIdRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    search_tag_id: Optional[str] = None


class ListSearchTagsResponseSchema(PaginateResponseSchema):
    search_tags: List[SearchTagSchema]


class CreateSearchTagResponseSchema(BaseResponseSchema):
    search_tag: SearchTagSchema


class CreateSearchTagsResponseSchema(BaseResponseSchema):
    search_tags: List[SearchTagSchema]


class UpdateSearchTagResponseSchema(BaseResponseSchema):
    search_tag: SearchTagSchema


class GetSearchTagByIdResponseSchema(BaseResponseSchema):
    search_tag: SearchTagSchema
