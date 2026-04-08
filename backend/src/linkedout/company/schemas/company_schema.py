# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for Company."""
from datetime import datetime
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CompanySchema(BaseModel):
    id: Annotated[str, Field(description='Unique company ID')]
    canonical_name: Annotated[str, Field(description='Canonical company name')]
    normalized_name: Annotated[str, Field(description='Normalized name for matching')]
    linkedin_url: Annotated[Optional[str], Field(default=None, description='LinkedIn URL')]
    universal_name: Annotated[Optional[str], Field(default=None, description='LinkedIn universal name')]
    website: Annotated[Optional[str], Field(default=None, description='Company website')]
    domain: Annotated[Optional[str], Field(default=None, description='Company email domain')]
    industry: Annotated[Optional[str], Field(default=None, description='Company industry')]
    founded_year: Annotated[Optional[int], Field(default=None, description='Founded year')]
    hq_city: Annotated[Optional[str], Field(default=None, description='HQ City')]
    hq_country: Annotated[Optional[str], Field(default=None, description='HQ Country')]
    employee_count_range: Annotated[Optional[str], Field(default=None, description='Employee count bracket')]
    estimated_employee_count: Annotated[Optional[int], Field(default=None, description='Estimated employees')]
    size_tier: Annotated[Optional[str], Field(default=None, description='Size categorization tier')]
    network_connection_count: Annotated[int, Field(default=0, description='Known network connections')]
    parent_company_id: Annotated[Optional[str], Field(default=None, description='Parent company ID')]
    enrichment_sources: Annotated[Optional[List[str]], Field(default=None, description='Data enrichment sources')]
    enriched_at: Annotated[Optional[datetime], Field(default=None, description='Timestamp of last enrichment')]
    created_at: Annotated[datetime, Field(description='Creation time')]
    updated_at: Annotated[datetime, Field(description='Update time')]

    model_config = ConfigDict(from_attributes=True)
