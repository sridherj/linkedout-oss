# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for Education."""
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


class EducationSchema(BaseModel):
    id: Annotated[str, Field(description='Unique ID')]
    crawled_profile_id: Annotated[str, Field(description='Profile this education belongs to')]
    school_name: Annotated[Optional[str], Field(default=None, description='Name of the school/university')]
    school_linkedin_url: Annotated[Optional[str], Field(default=None, description='LinkedIn URL of the school')]
    degree: Annotated[Optional[str], Field(default=None, description='Degree obtained')]
    field_of_study: Annotated[Optional[str], Field(default=None, description='Field of study / major')]
    start_year: Annotated[Optional[int], Field(default=None, description='Year started')]
    end_year: Annotated[Optional[int], Field(default=None, description='Year ended or expected to end')]
    description: Annotated[Optional[str], Field(default=None, description='Additional description about the education')]
    raw_education: Annotated[Optional[str], Field(default=None, description='Raw JSON payload of education data')]
    created_at: Annotated[datetime, Field(description='Creation time')]
    updated_at: Annotated[datetime, Field(description='Update time')]

    model_config = ConfigDict(from_attributes=True)
