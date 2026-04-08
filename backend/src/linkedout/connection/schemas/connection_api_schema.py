# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for Connection API."""
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.connection.schemas.connection_schema import ConnectionSchema


class ConnectionSortByFields(StrEnum):
    CREATED_AT = 'created_at'
    UPDATED_AT = 'updated_at'
    AFFINITY_SCORE = 'affinity_score'
    CONNECTED_AT = 'connected_at'
    DUNBAR_TIER = 'dunbar_tier'


class ListConnectionsRequestSchema(PaginateRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='Business Unit ID')]
    sort_by: Annotated[ConnectionSortByFields, Field(default=ConnectionSortByFields.CREATED_AT, description='Field to sort by')]
    sort_order: Annotated[SortOrder, Field(default=SortOrder.DESC, description='Sort direction')]
    app_user_id: Annotated[Optional[str], Field(default=None, description='Filter by App User')]
    crawled_profile_id: Annotated[Optional[str], Field(default=None, description='Filter by linked profile')]
    dunbar_tier: Annotated[Optional[str], Field(default=None, description='Filter by Dunbar tier')]
    affinity_score_min: Annotated[Optional[float], Field(default=None, description='Minimum affinity score')]
    affinity_score_max: Annotated[Optional[float], Field(default=None, description='Maximum affinity score')]


class CreateConnectionRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='Business Unit ID')]
    app_user_id: Annotated[str, Field(description='User who owns this connection')]
    crawled_profile_id: Annotated[str, Field(description='Profile representing the connected person')]
    connected_at: Annotated[Optional[date], Field(default=None, description='When the connection was established')]
    emails: Annotated[Optional[str], Field(default=None, description='Comma-separated emails')]
    phones: Annotated[Optional[str], Field(default=None, description='Comma-separated phones')]
    notes: Annotated[Optional[str], Field(default=None, description='Personal notes')]
    tags: Annotated[Optional[str], Field(default=None, description='Comma-separated tags')]
    sources: Annotated[Optional[List[str]], Field(default=None, description='Sources of connection')]
    source_details: Annotated[Optional[str], Field(default=None, description='Raw JSON data')]
    affinity_score: Annotated[Optional[float], Field(default=None, description='Calculated affinity score')]
    dunbar_tier: Annotated[Optional[str], Field(default=None, description='Assigned Dunbar tier')]
    affinity_source_count: Annotated[float, Field(default=0, description='Number of interaction sources')]
    affinity_recency: Annotated[float, Field(default=0, description='Recency dimension')]
    affinity_career_overlap: Annotated[float, Field(default=0, description='Career overlap dimension')]
    affinity_mutual_connections: Annotated[float, Field(default=0, description='Mutual connections dimension')]
    affinity_computed_at: Annotated[Optional[datetime], Field(default=None, description='When affinity logic ran')]
    affinity_version: Annotated[int, Field(default=0, description='Affinity logic version')]


class CreateConnectionsRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='Business Unit ID')]
    connections: Annotated[List[CreateConnectionRequestSchema], Field(description='List of connections to create')]


class UpdateConnectionRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='Business Unit ID')]
    connection_id: Annotated[Optional[str], Field(default=None, description='Connection ID')]
    connected_at: Annotated[Optional[date], Field(default=None, description='Updated connection date')]
    emails: Annotated[Optional[str], Field(default=None, description='Updated emails')]
    phones: Annotated[Optional[str], Field(default=None, description='Updated phones')]
    notes: Annotated[Optional[str], Field(default=None, description='Updated notes')]
    tags: Annotated[Optional[str], Field(default=None, description='Updated tags')]
    sources: Annotated[Optional[List[str]], Field(default=None, description='Updated sources')]
    source_details: Annotated[Optional[str], Field(default=None, description='Updated source details')]
    affinity_score: Annotated[Optional[float], Field(default=None, description='Updated affinity score')]
    dunbar_tier: Annotated[Optional[str], Field(default=None, description='Updated Dunbar tier')]
    affinity_source_count: Annotated[Optional[float], Field(default=None, description='Updated interaction sources')]
    affinity_recency: Annotated[Optional[float], Field(default=None, description='Updated recency score')]
    affinity_career_overlap: Annotated[Optional[float], Field(default=None, description='Updated career overlap score')]
    affinity_mutual_connections: Annotated[Optional[float], Field(default=None, description='Updated mutual connections score')]
    affinity_computed_at: Annotated[Optional[datetime], Field(default=None, description='Updated affinity computation time')]
    affinity_version: Annotated[Optional[int], Field(default=None, description='Updated affinity algorithm version')]


class GetConnectionByIdRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='Business Unit ID')]
    connection_id: Annotated[Optional[str], Field(default=None, description='Connection ID')]


class DeleteConnectionByIdRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='Business Unit ID')]
    connection_id: Annotated[Optional[str], Field(default=None, description='Connection ID')]


class ListConnectionsResponseSchema(PaginateResponseSchema):
    connections: Annotated[List[ConnectionSchema], Field(description='List of matching connections')]


class CreateConnectionResponseSchema(BaseResponseSchema):
    connection: Annotated[ConnectionSchema, Field(description='Created connection')]


class CreateConnectionsResponseSchema(BaseResponseSchema):
    connections: Annotated[List[ConnectionSchema], Field(description='Created connections')]


class UpdateConnectionResponseSchema(BaseResponseSchema):
    connection: Annotated[ConnectionSchema, Field(description='Updated connection')]


class GetConnectionByIdResponseSchema(BaseResponseSchema):
    connection: Annotated[ConnectionSchema, Field(description='Fetched connection')]
