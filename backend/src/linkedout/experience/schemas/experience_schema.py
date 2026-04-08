# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for Experience."""
from datetime import date, datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


class ExperienceSchema(BaseModel):
    id: Annotated[str, Field(description='Primary key')]
    crawled_profile_id: Annotated[str, Field(description='Profile this experience belongs to')]
    position: Annotated[Optional[str], Field(description='Job title or position', default=None)]
    position_normalized: Annotated[Optional[str], Field(description='Normalized job title', default=None)]
    company_name: Annotated[Optional[str], Field(description='Name of the company', default=None)]
    company_id: Annotated[Optional[str], Field(description='Resolved company entity ID if matched', default=None)]
    company_linkedin_url: Annotated[Optional[str], Field(description='LinkedIn URL of the company', default=None)]
    employment_type: Annotated[Optional[str], Field(description='Type of employment (full-time, part-time, etc)', default=None)]
    start_date: Annotated[Optional[date], Field(description='Start date of role', default=None)]
    start_year: Annotated[Optional[int], Field(description='Start year', default=None)]
    start_month: Annotated[Optional[int], Field(description='Start month', default=None)]
    end_date: Annotated[Optional[date], Field(description='End date of role', default=None)]
    end_year: Annotated[Optional[int], Field(description='End year', default=None)]
    end_month: Annotated[Optional[int], Field(description='End month', default=None)]
    end_date_text: Annotated[Optional[str], Field(description='Textual end date like "Present"', default=None)]
    is_current: Annotated[Optional[bool], Field(description='Whether this is the current role', default=None)]
    seniority_level: Annotated[Optional[str], Field(description='Estimated seniority level', default=None)]
    function_area: Annotated[Optional[str], Field(description='Function area or department', default=None)]
    location: Annotated[Optional[str], Field(description='Location of the role', default=None)]
    description: Annotated[Optional[str], Field(description='Description of the role/experience', default=None)]
    raw_experience: Annotated[Optional[str], Field(description='Raw JSON payload of experience data', default=None)]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
