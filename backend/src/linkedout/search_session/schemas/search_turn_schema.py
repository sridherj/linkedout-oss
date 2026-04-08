# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for SearchTurn."""
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


class SearchTurnSchema(BaseModel):
    id: Annotated[str, Field(description='Primary key')]
    tenant_id: Annotated[str, Field(description='Tenant ID')]
    bu_id: Annotated[str, Field(description='Business Unit ID')]
    session_id: Annotated[str, Field(description='Parent search session ID')]
    turn_number: Annotated[int, Field(description='1-indexed turn number')]
    user_query: Annotated[str, Field(description='User query for this turn')]
    transcript: Annotated[Optional[dict], Field(description='Full LLM messages array', default=None)]
    results: Annotated[Optional[list], Field(description='Structured result set', default=None)]
    summary: Annotated[Optional[str], Field(description='LLM-generated summary', default=None)]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
