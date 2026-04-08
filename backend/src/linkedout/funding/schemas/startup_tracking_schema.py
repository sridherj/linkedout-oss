# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for StartupTracking."""
from datetime import date, datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


class StartupTrackingSchema(BaseModel):
    id: Annotated[str, Field(description='Unique startup tracking ID')]
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
    created_at: Annotated[datetime, Field(description='Creation time')]
    updated_at: Annotated[datetime, Field(description='Update time')]

    model_config = ConfigDict(from_attributes=True)
