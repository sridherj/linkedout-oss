# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for FundingRound API."""
from datetime import date
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.funding.schemas.funding_round_schema import FundingRoundSchema


class FundingRoundSortByFields(StrEnum):
    ANNOUNCED_ON = 'announced_on'
    AMOUNT_USD = 'amount_usd'
    CREATED_AT = 'created_at'


class ListFundingRoundsRequestSchema(PaginateRequestSchema):
    sort_by: Annotated[FundingRoundSortByFields, Field(default=FundingRoundSortByFields.CREATED_AT, description='Field to sort by')]
    sort_order: Annotated[SortOrder, Field(default=SortOrder.DESC, description='Sort direction')]
    company_id: Annotated[Optional[str], Field(default=None, description='Filter by company ID')]
    round_type: Annotated[Optional[str], Field(default=None, description='Filter by round type')]


class CreateFundingRoundRequestSchema(BaseRequestSchema):
    company_id: Annotated[str, Field(description='FK to company')]
    round_type: Annotated[str, Field(description='Seed, Series A, etc.')]
    announced_on: Annotated[Optional[date], Field(default=None, description='Announcement date')]
    amount_usd: Annotated[Optional[int], Field(default=None, description='Round amount in USD')]
    lead_investors: Annotated[Optional[List[str]], Field(default=None, description='Lead investor names')]
    all_investors: Annotated[Optional[List[str]], Field(default=None, description='All investor names')]
    source_url: Annotated[Optional[str], Field(default=None, description='Source article URL')]
    confidence: Annotated[int, Field(default=5, description='Confidence score 1-10')]
    source: Annotated[Optional[str], Field(default=None, description='Data origin')]
    notes: Annotated[Optional[str], Field(default=None, description='Additional notes')]


class UpdateFundingRoundRequestSchema(BaseRequestSchema):
    funding_round_id: Annotated[Optional[str], Field(default=None, description='Funding round ID')]
    round_type: Annotated[Optional[str], Field(default=None, description='Updated round type')]
    announced_on: Annotated[Optional[date], Field(default=None, description='Updated announcement date')]
    amount_usd: Annotated[Optional[int], Field(default=None, description='Updated amount')]
    lead_investors: Annotated[Optional[List[str]], Field(default=None, description='Updated lead investors')]
    all_investors: Annotated[Optional[List[str]], Field(default=None, description='Updated all investors')]
    source_url: Annotated[Optional[str], Field(default=None, description='Updated source URL')]
    confidence: Annotated[Optional[int], Field(default=None, description='Updated confidence')]
    source: Annotated[Optional[str], Field(default=None, description='Updated source')]
    notes: Annotated[Optional[str], Field(default=None, description='Updated notes')]


class GetFundingRoundByIdRequestSchema(BaseRequestSchema):
    funding_round_id: Annotated[Optional[str], Field(default=None, description='Funding round ID')]


class DeleteFundingRoundByIdRequestSchema(BaseRequestSchema):
    funding_round_id: Annotated[Optional[str], Field(default=None, description='Funding round ID')]


class ListFundingRoundsResponseSchema(PaginateResponseSchema):
    funding_rounds: Annotated[List[FundingRoundSchema], Field(description='List of funding rounds')]


class CreateFundingRoundResponseSchema(BaseResponseSchema):
    funding_round: Annotated[FundingRoundSchema, Field(description='The created funding round')]


class UpdateFundingRoundResponseSchema(BaseResponseSchema):
    funding_round: Annotated[FundingRoundSchema, Field(description='The updated funding round')]


class GetFundingRoundByIdResponseSchema(BaseResponseSchema):
    funding_round: Annotated[FundingRoundSchema, Field(description='The returned funding round')]
