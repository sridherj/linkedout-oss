# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for CrawledProfile API."""
from enum import StrEnum
from typing import Annotated, Any, List, Optional

from pydantic import BaseModel, Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.crawled_profile.schemas.crawled_profile_schema import CrawledProfileSchema


class CrawledProfileSortByFields(StrEnum):
    FULL_NAME = 'full_name'
    CREATED_AT = 'created_at'
    CURRENT_COMPANY_NAME = 'current_company_name'
    SENIORITY_LEVEL = 'seniority_level'
    DATA_SOURCE = 'data_source'


class ListCrawledProfilesRequestSchema(PaginateRequestSchema):
    sort_by: Annotated[CrawledProfileSortByFields, Field(default=CrawledProfileSortByFields.CREATED_AT, description='Sort field')]
    sort_order: Annotated[SortOrder, Field(default=SortOrder.DESC, description='Sort order')]
    full_name: Annotated[Optional[str], Field(default=None, description='Filter by full name')]
    current_company_name: Annotated[Optional[str], Field(default=None, description='Filter by current company')]
    company_id: Annotated[Optional[str], Field(default=None, description='Filter by internal company ID')]
    seniority_level: Annotated[Optional[str], Field(default=None, description='Filter by seniority level')]
    function_area: Annotated[Optional[str], Field(default=None, description='Filter by function area')]
    data_source: Annotated[Optional[str], Field(default=None, description='Filter by data source')]
    has_enriched_data: Annotated[Optional[bool], Field(default=None, description='Filter by enriched status')]
    location_country_code: Annotated[Optional[str], Field(default=None, description='Filter by country code')]
    crawled_profile_ids: Annotated[Optional[List[str]], Field(default=None, description='Filter by exact subset of crawled_profile_ids')]
    linkedin_url: Annotated[Optional[str], Field(default=None, description='Filter by exact LinkedIn URL')]


class CreateCrawledProfileRequestSchema(BaseRequestSchema):
    linkedin_url: Annotated[str, Field(description='Full LinkedIn URL')]
    public_identifier: Annotated[Optional[str], Field(default=None, description='LinkedIn public identifier token')]
    first_name: Annotated[Optional[str], Field(default=None, description='First name')]
    last_name: Annotated[Optional[str], Field(default=None, description='Last name')]
    full_name: Annotated[Optional[str], Field(default=None, description='Full name')]
    headline: Annotated[Optional[str], Field(default=None, description='Profile headline')]
    about: Annotated[Optional[str], Field(default=None, description='Profile about section')]
    location_city: Annotated[Optional[str], Field(default=None, description='City location')]
    location_state: Annotated[Optional[str], Field(default=None, description='State/province location')]
    location_country: Annotated[Optional[str], Field(default=None, description='Country location')]
    location_country_code: Annotated[Optional[str], Field(default=None, description='ISO country code')]
    location_raw: Annotated[Optional[str], Field(default=None, description='Raw location string')]
    connections_count: Annotated[Optional[int], Field(default=None, description='Total number of connections')]
    follower_count: Annotated[Optional[int], Field(default=None, description='Total number of followers')]
    open_to_work: Annotated[Optional[bool], Field(default=None, description='Is the profile open to work')]
    premium: Annotated[Optional[bool], Field(default=None, description='Is it a premium account')]
    current_company_name: Annotated[Optional[str], Field(default=None, description='Name of the current company')]
    current_position: Annotated[Optional[str], Field(default=None, description='Current job title/position')]
    company_id: Annotated[Optional[str], Field(default=None, description='Resolved internal company ID')]
    seniority_level: Annotated[Optional[str], Field(default=None, description='Deduced seniority level')]
    function_area: Annotated[Optional[str], Field(default=None, description='Deduced function/department area')]
    source_app_user_id: Annotated[Optional[str], Field(default=None, description='User who initiated the crawl, if any')]
    data_source: Annotated[str, Field(description='Source of data collection (e.g. extension, api)')]
    has_enriched_data: Annotated[bool, Field(default=False, description='Whether extended enrichment has been applied')]
    last_crawled_at: Annotated[Optional[str], Field(default=None, description='When this profile was last crawled/synced')]
    profile_image_url: Annotated[Optional[str], Field(default=None, description='URL to profile image')]
    raw_profile: Annotated[Optional[Any], Field(default=None, description='Raw JSON payload of the profile data')]


class CreateCrawledProfilesRequestSchema(BaseRequestSchema):
    crawled_profiles: Annotated[List[CreateCrawledProfileRequestSchema], Field(description='List of items to create')]


class UpdateCrawledProfileRequestSchema(BaseRequestSchema):
    crawled_profile_id: Annotated[Optional[str], Field(default=None, description='ID of the profile to update')]
    linkedin_url: Annotated[Optional[str], Field(default=None, description='Full LinkedIn URL')]
    public_identifier: Annotated[Optional[str], Field(default=None, description='LinkedIn public identifier token')]
    first_name: Annotated[Optional[str], Field(default=None, description='First name')]
    last_name: Annotated[Optional[str], Field(default=None, description='Last name')]
    full_name: Annotated[Optional[str], Field(default=None, description='Full name')]
    headline: Annotated[Optional[str], Field(default=None, description='Profile headline')]
    about: Annotated[Optional[str], Field(default=None, description='Profile about section')]
    location_city: Annotated[Optional[str], Field(default=None, description='City location')]
    location_state: Annotated[Optional[str], Field(default=None, description='State/province location')]
    location_country: Annotated[Optional[str], Field(default=None, description='Country location')]
    location_country_code: Annotated[Optional[str], Field(default=None, description='ISO country code')]
    location_raw: Annotated[Optional[str], Field(default=None, description='Raw location string')]
    connections_count: Annotated[Optional[int], Field(default=None, description='Total number of connections')]
    follower_count: Annotated[Optional[int], Field(default=None, description='Total number of followers')]
    open_to_work: Annotated[Optional[bool], Field(default=None, description='Is the profile open to work')]
    premium: Annotated[Optional[bool], Field(default=None, description='Is it a premium account')]
    current_company_name: Annotated[Optional[str], Field(default=None, description='Name of the current company')]
    current_position: Annotated[Optional[str], Field(default=None, description='Current job title/position')]
    company_id: Annotated[Optional[str], Field(default=None, description='Resolved internal company ID')]
    seniority_level: Annotated[Optional[str], Field(default=None, description='Deduced seniority level')]
    function_area: Annotated[Optional[str], Field(default=None, description='Deduced function/department area')]
    source_app_user_id: Annotated[Optional[str], Field(default=None, description='User who initiated the crawl, if any')]
    data_source: Annotated[Optional[str], Field(default=None, description='Source of data collection')]
    has_enriched_data: Annotated[Optional[bool], Field(default=None, description='Whether extended enrichment has been applied')]
    last_crawled_at: Annotated[Optional[str], Field(default=None, description='When this profile was last crawled/synced')]
    profile_image_url: Annotated[Optional[str], Field(default=None, description='URL to profile image')]
    raw_profile: Annotated[Optional[Any], Field(default=None, description='Raw JSON payload of the profile data')]


class GetCrawledProfileByIdRequestSchema(BaseRequestSchema):
    crawled_profile_id: Annotated[Optional[str], Field(default=None, description='ID of the profile to retrieve')]


class DeleteCrawledProfileByIdRequestSchema(BaseRequestSchema):
    crawled_profile_id: Annotated[Optional[str], Field(default=None, description='ID of the profile to delete')]


class ListCrawledProfilesResponseSchema(PaginateResponseSchema):
    crawled_profiles: Annotated[List[CrawledProfileSchema], Field(description='List of profiles')]


class CreateCrawledProfileResponseSchema(BaseResponseSchema):
    crawled_profile: Annotated[CrawledProfileSchema, Field(description='Created profile')]


class CreateCrawledProfilesResponseSchema(BaseResponseSchema):
    crawled_profiles: Annotated[List[CrawledProfileSchema], Field(description='Created profiles')]


class UpdateCrawledProfileResponseSchema(BaseResponseSchema):
    crawled_profile: Annotated[CrawledProfileSchema, Field(description='Updated profile')]


class GetCrawledProfileByIdResponseSchema(BaseResponseSchema):
    crawled_profile: Annotated[CrawledProfileSchema, Field(description='Retrieved profile')]


class EnrichExperienceItem(BaseModel):
    """Single experience entry. Caller normalizes source-specific formats."""
    position: str | None = None
    company_name: str | None = None
    company_linkedin_url: str | None = None
    company_universal_name: str | None = None
    employment_type: str | None = None
    start_year: int | None = None
    start_month: int | None = None
    end_year: int | None = None
    end_month: int | None = None
    is_current: bool | None = None
    location: str | None = None
    description: str | None = None


class EnrichEducationItem(BaseModel):
    """Single education entry."""
    school_name: str | None = None
    school_linkedin_url: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    description: str | None = None


class EnrichProfileRequestSchema(BaseModel):
    """Canonical enrichment payload. Both extension and Apify transform to this."""
    experiences: list[EnrichExperienceItem] = []
    educations: list[EnrichEducationItem] = []
    skills: list[str] = []


class EnrichProfileResponseSchema(BaseModel):
    experiences_created: int
    educations_created: int
    skills_created: int
