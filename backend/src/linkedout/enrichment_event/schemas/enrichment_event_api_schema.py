# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for EnrichmentEvent API."""
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.enrichment_event.schemas.enrichment_event_schema import EnrichmentEventSchema


class EnrichmentEventSortByFields(StrEnum):
    CREATED_AT = 'created_at'
    UPDATED_AT = 'updated_at'
    EVENT_TYPE = 'event_type'
    ENRICHMENT_MODE = 'enrichment_mode'


class ListEnrichmentEventsRequestSchema(PaginateRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='BU ID')]
    sort_by: Annotated[EnrichmentEventSortByFields, Field(default=EnrichmentEventSortByFields.CREATED_AT, description='Sort field')]
    sort_order: Annotated[SortOrder, Field(default=SortOrder.DESC, description='Sort order')]
    app_user_id: Annotated[Optional[str], Field(default=None, description='Filter by user ID')]
    crawled_profile_id: Annotated[Optional[str], Field(default=None, description='Filter by profile ID')]
    event_type: Annotated[Optional[str], Field(default=None, description='Filter by event type')]
    enrichment_mode: Annotated[Optional[str], Field(default=None, description='Filter by enrichment mode')]


class CreateEnrichmentEventRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='BU ID')]
    app_user_id: Annotated[str, Field(description='User who initiated the enrichment')]
    crawled_profile_id: Annotated[str, Field(description='Profile this enrichment targets')]
    event_type: Annotated[str, Field(description='Type of enrichment event')]
    enrichment_mode: Annotated[str, Field(description='Mode of enrichment')]
    crawler_name: Annotated[Optional[str], Field(default=None, description='Name of the crawler used')]
    cost_estimate_usd: Annotated[float, Field(default=0, description='Estimated cost in USD')]
    crawler_run_id: Annotated[Optional[str], Field(default=None, description='ID of the crawler run')]


class CreateEnrichmentEventsRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='BU ID')]
    enrichment_events: Annotated[List[CreateEnrichmentEventRequestSchema], Field(description='List of events to create')]


class UpdateEnrichmentEventRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='BU ID')]
    enrichment_event_id: Annotated[Optional[str], Field(default=None, description='ID of the event to update')]
    event_type: Annotated[Optional[str], Field(default=None, description='Type of enrichment event')]
    enrichment_mode: Annotated[Optional[str], Field(default=None, description='Mode of enrichment')]
    crawler_name: Annotated[Optional[str], Field(default=None, description='Name of the crawler used')]
    cost_estimate_usd: Annotated[Optional[float], Field(default=None, description='Estimated cost in USD')]
    crawler_run_id: Annotated[Optional[str], Field(default=None, description='ID of the crawler run')]


class GetEnrichmentEventByIdRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='BU ID')]
    enrichment_event_id: Annotated[Optional[str], Field(default=None, description='ID of the event to retrieve')]


class DeleteEnrichmentEventByIdRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='BU ID')]
    enrichment_event_id: Annotated[Optional[str], Field(default=None, description='ID of the event to delete')]


class ListEnrichmentEventsResponseSchema(PaginateResponseSchema):
    enrichment_events: Annotated[List[EnrichmentEventSchema], Field(description='List of events')]


class CreateEnrichmentEventResponseSchema(BaseResponseSchema):
    enrichment_event: Annotated[EnrichmentEventSchema, Field(description='Created event')]


class CreateEnrichmentEventsResponseSchema(BaseResponseSchema):
    enrichment_events: Annotated[List[EnrichmentEventSchema], Field(description='Created events')]


class UpdateEnrichmentEventResponseSchema(BaseResponseSchema):
    enrichment_event: Annotated[EnrichmentEventSchema, Field(description='Updated event')]


class GetEnrichmentEventByIdResponseSchema(BaseResponseSchema):
    enrichment_event: Annotated[EnrichmentEventSchema, Field(description='Retrieved event')]
