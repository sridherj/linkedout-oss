# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for GrowthSignal."""
from datetime import date, datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


class GrowthSignalSchema(BaseModel):
    id: Annotated[str, Field(description='Unique growth signal ID')]
    company_id: Annotated[str, Field(description='FK to company')]
    signal_type: Annotated[str, Field(description='arr, mrr, revenue, headcount, etc.')]
    signal_date: Annotated[date, Field(description='Date signal was observed')]
    value_numeric: Annotated[Optional[int], Field(default=None, description='Numeric value')]
    value_text: Annotated[Optional[str], Field(default=None, description='Human-readable description')]
    source_url: Annotated[Optional[str], Field(default=None, description='Source URL')]
    confidence: Annotated[int, Field(default=5, description='Confidence score 1-10')]
    source: Annotated[Optional[str], Field(default=None, description='Data origin')]
    notes: Annotated[Optional[str], Field(default=None, description='Additional notes')]
    created_at: Annotated[datetime, Field(description='Creation time')]
    updated_at: Annotated[datetime, Field(description='Update time')]

    model_config = ConfigDict(from_attributes=True)
