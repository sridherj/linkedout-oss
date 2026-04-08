# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for Company API."""
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.company.schemas.company_schema import CompanySchema


class CompanySortByFields(StrEnum):
    CANONICAL_NAME = 'canonical_name'
    CREATED_AT = 'created_at'
    INDUSTRY = 'industry'
    SIZE_TIER = 'size_tier'


class ListCompaniesRequestSchema(PaginateRequestSchema):
    sort_by: Annotated[CompanySortByFields, Field(default=CompanySortByFields.CANONICAL_NAME, description='Field to sort by')]
    sort_order: Annotated[SortOrder, Field(default=SortOrder.ASC, description='Sort direction')]
    canonical_name: Annotated[Optional[str], Field(default=None, description='Filter by partial canonical name')]
    domain: Annotated[Optional[str], Field(default=None, description='Exact filter by domain')]
    industry: Annotated[Optional[str], Field(default=None, description='Exact filter by industry')]
    size_tier: Annotated[Optional[str], Field(default=None, description='Exact filter by size tier')]
    hq_country: Annotated[Optional[str], Field(default=None, description='Exact filter by HQ country')]
    company_ids: Annotated[Optional[list[str]], Field(default=None, description='List of precise company IDs')]


class CreateCompanyRequestSchema(BaseRequestSchema):
    canonical_name: Annotated[str, Field(description='Company canonical name')]
    normalized_name: Annotated[str, Field(description='Normalized name')]
    linkedin_url: Annotated[Optional[str], Field(default=None, description='LinkedIn URL')]
    universal_name: Annotated[Optional[str], Field(default=None, description='LinkedIn universe name')]
    website: Annotated[Optional[str], Field(default=None, description='Website URL')]
    domain: Annotated[Optional[str], Field(default=None, description='Primary domain')]
    industry: Annotated[Optional[str], Field(default=None, description='Industry descriptor')]
    founded_year: Annotated[Optional[int], Field(default=None, description='Founded year')]
    hq_city: Annotated[Optional[str], Field(default=None, description='HQ city')]
    hq_country: Annotated[Optional[str], Field(default=None, description='HQ country code')]
    employee_count_range: Annotated[Optional[str], Field(default=None, description='Employee range bracket')]
    estimated_employee_count: Annotated[Optional[int], Field(default=None, description='Exact estimated employee count')]
    size_tier: Annotated[Optional[str], Field(default=None, description='Size tier class')]
    network_connection_count: Annotated[int, Field(default=0, description='Discovered direct connection count')]
    parent_company_id: Annotated[Optional[str], Field(default=None, description='ID of parent company')]
    enrichment_sources: Annotated[Optional[List[str]], Field(default=None, description='Sources of enrichment data')]


class CreateCompaniesRequestSchema(BaseRequestSchema):
    companies: Annotated[List[CreateCompanyRequestSchema], Field(description='Companies to create')]


class UpdateCompanyRequestSchema(BaseRequestSchema):
    company_id: Annotated[Optional[str], Field(default=None, description='Company ID')]
    canonical_name: Annotated[Optional[str], Field(default=None, description='Updated canonical name')]
    normalized_name: Annotated[Optional[str], Field(default=None, description='Updated normalized name')]
    linkedin_url: Annotated[Optional[str], Field(default=None, description='Updated LinkedIn URL')]
    universal_name: Annotated[Optional[str], Field(default=None, description='Updated universal name')]
    website: Annotated[Optional[str], Field(default=None, description='Updated website')]
    domain: Annotated[Optional[str], Field(default=None, description='Updated domain')]
    industry: Annotated[Optional[str], Field(default=None, description='Updated industry')]
    founded_year: Annotated[Optional[int], Field(default=None, description='Updated founded year')]
    hq_city: Annotated[Optional[str], Field(default=None, description='Updated HQ city')]
    hq_country: Annotated[Optional[str], Field(default=None, description='Updated HQ country')]
    employee_count_range: Annotated[Optional[str], Field(default=None, description='Updated employee range')]
    estimated_employee_count: Annotated[Optional[int], Field(default=None, description='Updated employee count')]
    size_tier: Annotated[Optional[str], Field(default=None, description='Updated size tier')]
    network_connection_count: Annotated[Optional[int], Field(default=None, description='Updated network connection count')]
    parent_company_id: Annotated[Optional[str], Field(default=None, description='Updated parent company ID')]
    enrichment_sources: Annotated[Optional[List[str]], Field(default=None, description='Updated enrichment sources')]


class GetCompanyByIdRequestSchema(BaseRequestSchema):
    company_id: Annotated[Optional[str], Field(default=None, description='Company ID')]


class DeleteCompanyByIdRequestSchema(BaseRequestSchema):
    company_id: Annotated[Optional[str], Field(default=None, description='Company ID')]


class ListCompaniesResponseSchema(PaginateResponseSchema):
    companies: Annotated[List[CompanySchema], Field(description='List of returned companies')]


class CreateCompanyResponseSchema(BaseResponseSchema):
    company: Annotated[CompanySchema, Field(description='The created company')]


class CreateCompaniesResponseSchema(BaseResponseSchema):
    companies: Annotated[List[CompanySchema], Field(description='The created companies')]


class UpdateCompanyResponseSchema(BaseResponseSchema):
    company: Annotated[CompanySchema, Field(description='The updated company')]


class GetCompanyByIdResponseSchema(BaseResponseSchema):
    company: Annotated[CompanySchema, Field(description='The returned company')]
