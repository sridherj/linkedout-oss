# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for FundingRound."""
from datetime import date, datetime
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FundingRoundSchema(BaseModel):
    id: Annotated[str, Field(description='Unique funding round ID')]
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
    created_at: Annotated[datetime, Field(description='Creation time')]
    updated_at: Annotated[datetime, Field(description='Update time')]

    model_config = ConfigDict(from_attributes=True)
