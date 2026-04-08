# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for SearchSession."""
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


class SearchSessionSchema(BaseModel):
    id: Annotated[str, Field(description='Primary key')]
    tenant_id: Annotated[str, Field(description='Tenant ID')]
    bu_id: Annotated[str, Field(description='Business Unit ID')]
    app_user_id: Annotated[str, Field(description='User who owns the session')]
    initial_query: Annotated[str, Field(description='First search query')]
    turn_count: Annotated[int, Field(description='Number of conversation turns', default=1)]
    last_active_at: datetime
    is_saved: Annotated[bool, Field(description='Whether this session is saved/bookmarked', default=False)]
    saved_name: Annotated[Optional[str], Field(description='User-provided name for the saved session', default=None)]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
