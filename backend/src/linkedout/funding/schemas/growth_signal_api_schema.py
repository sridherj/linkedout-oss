# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for GrowthSignal API."""
from datetime import date
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.funding.schemas.growth_signal_schema import GrowthSignalSchema


class GrowthSignalSortByFields(StrEnum):
    SIGNAL_DATE = 'signal_date'
    SIGNAL_TYPE = 'signal_type'
    CREATED_AT = 'created_at'


class ListGrowthSignalsRequestSchema(PaginateRequestSchema):
    sort_by: Annotated[GrowthSignalSortByFields, Field(default=GrowthSignalSortByFields.CREATED_AT, description='Field to sort by')]
    sort_order: Annotated[SortOrder, Field(default=SortOrder.DESC, description='Sort direction')]
    company_id: Annotated[Optional[str], Field(default=None, description='Filter by company ID')]
    signal_type: Annotated[Optional[str], Field(default=None, description='Filter by signal type')]


class CreateGrowthSignalRequestSchema(BaseRequestSchema):
    company_id: Annotated[str, Field(description='FK to company')]
    signal_type: Annotated[str, Field(description='arr, mrr, revenue, headcount, etc.')]
    signal_date: Annotated[date, Field(description='Date signal was observed')]
    value_numeric: Annotated[Optional[int], Field(default=None, description='Numeric value')]
    value_text: Annotated[Optional[str], Field(default=None, description='Human-readable description')]
    source_url: Annotated[Optional[str], Field(default=None, description='Source URL')]
    confidence: Annotated[int, Field(default=5, description='Confidence score 1-10')]
    source: Annotated[Optional[str], Field(default=None, description='Data origin')]
    notes: Annotated[Optional[str], Field(default=None, description='Additional notes')]


class UpdateGrowthSignalRequestSchema(BaseRequestSchema):
    growth_signal_id: Annotated[Optional[str], Field(default=None, description='Growth signal ID')]
    signal_type: Annotated[Optional[str], Field(default=None, description='Updated signal type')]
    signal_date: Annotated[Optional[date], Field(default=None, description='Updated signal date')]
    value_numeric: Annotated[Optional[int], Field(default=None, description='Updated numeric value')]
    value_text: Annotated[Optional[str], Field(default=None, description='Updated text value')]
    source_url: Annotated[Optional[str], Field(default=None, description='Updated source URL')]
    confidence: Annotated[Optional[int], Field(default=None, description='Updated confidence')]
    source: Annotated[Optional[str], Field(default=None, description='Updated source')]
    notes: Annotated[Optional[str], Field(default=None, description='Updated notes')]


class GetGrowthSignalByIdRequestSchema(BaseRequestSchema):
    growth_signal_id: Annotated[Optional[str], Field(default=None, description='Growth signal ID')]


class DeleteGrowthSignalByIdRequestSchema(BaseRequestSchema):
    growth_signal_id: Annotated[Optional[str], Field(default=None, description='Growth signal ID')]


class ListGrowthSignalsResponseSchema(PaginateResponseSchema):
    growth_signals: Annotated[List[GrowthSignalSchema], Field(description='List of growth signals')]


class CreateGrowthSignalResponseSchema(BaseResponseSchema):
    growth_signal: Annotated[GrowthSignalSchema, Field(description='The created growth signal')]


class UpdateGrowthSignalResponseSchema(BaseResponseSchema):
    growth_signal: Annotated[GrowthSignalSchema, Field(description='The updated growth signal')]


class GetGrowthSignalByIdResponseSchema(BaseResponseSchema):
    growth_signal: Annotated[GrowthSignalSchema, Field(description='The returned growth signal')]
