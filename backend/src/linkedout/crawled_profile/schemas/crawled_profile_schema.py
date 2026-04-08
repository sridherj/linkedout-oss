# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for CrawledProfile."""
from datetime import datetime
from typing import Annotated, Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class CrawledProfileSchema(BaseModel):
    id: Annotated[str, Field(description='Unique ID')]
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
    embedding: Annotated[Optional[Any], Field(default=None, exclude=True, description='Vector embedding of profile data')]
    search_vector: Annotated[Optional[Any], Field(default=None, exclude=True, description='Text search vector')]
    source_app_user_id: Annotated[Optional[str], Field(default=None, description='User who initiated the crawl, if any')]
    data_source: Annotated[str, Field(description='Source of data collection (e.g. extension, api)')]
    has_enriched_data: Annotated[bool, Field(default=False, description='Whether extended enrichment has been applied')]
    last_crawled_at: Annotated[Optional[datetime], Field(default=None, description='When this profile was last crawled/synced')]
    profile_image_url: Annotated[Optional[str], Field(default=None, description='URL to profile image')]
    raw_profile: Annotated[Optional[Any], Field(default=None, description='Raw JSON payload of the profile data')]
    created_at: Annotated[datetime, Field(description='Creation time')]
    updated_at: Annotated[datetime, Field(description='Update time')]

    model_config = ConfigDict(from_attributes=True)
