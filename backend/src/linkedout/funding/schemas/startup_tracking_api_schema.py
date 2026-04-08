# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for StartupTracking API."""
from datetime import date
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.funding.schemas.startup_tracking_schema import StartupTrackingSchema


class StartupTrackingSortByFields(StrEnum):
    TOTAL_RAISED_USD = 'total_raised_usd'
    LAST_FUNDING_DATE = 'last_funding_date'
    CREATED_AT = 'created_at'


class ListStartupTrackingsRequestSchema(PaginateRequestSchema):
    sort_by: Annotated[StartupTrackingSortByFields, Field(default=StartupTrackingSortByFields.CREATED_AT, description='Field to sort by')]
    sort_order: Annotated[SortOrder, Field(default=SortOrder.DESC, description='Sort direction')]
    company_id: Annotated[Optional[str], Field(default=None, description='Filter by company ID')]
    watching: Annotated[Optional[bool], Field(default=None, description='Filter by watching flag')]
    vertical: Annotated[Optional[str], Field(default=None, description='Filter by vertical')]


class CreateStartupTrackingRequestSchema(BaseRequestSchema):
    company_id: Annotated[str, Field(description='FK to company')]
    watching: Annotated[bool, Field(default=False, description='Pipeline filter flag')]
    description: Annotated[Optional[str], Field(default=None, description='Startup description')]
    vertical: Annotated[Optional[str], Field(default=None, description='AI vertical')]
    sub_category: Annotated[Optional[str], Field(default=None, description='Finer classification')]
    funding_stage: Annotated[Optional[str], Field(default=None, description='Denormalized funding stage')]
    total_raised_usd: Annotated[Optional[int], Field(default=None, description='Denormalized sum')]
    last_funding_date: Annotated[Optional[date], Field(default=None, description='Denormalized latest')]
    round_count: Annotated[int, Field(default=0, description='Denormalized count')]
    estimated_arr_usd: Annotated[Optional[int], Field(default=None, description='Revenue estimate')]
    arr_signal_date: Annotated[Optional[date], Field(default=None, description='When ARR was estimated')]
    arr_confidence: Annotated[Optional[int], Field(default=None, description='Confidence 1-10')]
    source: Annotated[Optional[str], Field(default=None, description='Data origin')]
    notes: Annotated[Optional[str], Field(default=None, description='Additional notes')]


class UpdateStartupTrackingRequestSchema(BaseRequestSchema):
    startup_tracking_id: Annotated[Optional[str], Field(default=None, description='Startup tracking ID')]
    watching: Annotated[Optional[bool], Field(default=None, description='Updated watching flag')]
    description: Annotated[Optional[str], Field(default=None, description='Updated description')]
    vertical: Annotated[Optional[str], Field(default=None, description='Updated vertical')]
    sub_category: Annotated[Optional[str], Field(default=None, description='Updated sub category')]
    funding_stage: Annotated[Optional[str], Field(default=None, description='Updated funding stage')]
    total_raised_usd: Annotated[Optional[int], Field(default=None, description='Updated total raised')]
    last_funding_date: Annotated[Optional[date], Field(default=None, description='Updated last funding date')]
    round_count: Annotated[Optional[int], Field(default=None, description='Updated round count')]
    estimated_arr_usd: Annotated[Optional[int], Field(default=None, description='Updated ARR')]
    arr_signal_date: Annotated[Optional[date], Field(default=None, description='Updated ARR signal date')]
    arr_confidence: Annotated[Optional[int], Field(default=None, description='Updated ARR confidence')]
    source: Annotated[Optional[str], Field(default=None, description='Updated source')]
    notes: Annotated[Optional[str], Field(default=None, description='Updated notes')]


class GetStartupTrackingByIdRequestSchema(BaseRequestSchema):
    startup_tracking_id: Annotated[Optional[str], Field(default=None, description='Startup tracking ID')]


class DeleteStartupTrackingByIdRequestSchema(BaseRequestSchema):
    startup_tracking_id: Annotated[Optional[str], Field(default=None, description='Startup tracking ID')]


class ListStartupTrackingsResponseSchema(PaginateResponseSchema):
    startup_trackings: Annotated[List[StartupTrackingSchema], Field(description='List of startup trackings')]


class CreateStartupTrackingResponseSchema(BaseResponseSchema):
    startup_tracking: Annotated[StartupTrackingSchema, Field(description='The created startup tracking')]


class UpdateStartupTrackingResponseSchema(BaseResponseSchema):
    startup_tracking: Annotated[StartupTrackingSchema, Field(description='The updated startup tracking')]


class GetStartupTrackingByIdResponseSchema(BaseResponseSchema):
    startup_tracking: Annotated[StartupTrackingSchema, Field(description='The returned startup tracking')]
