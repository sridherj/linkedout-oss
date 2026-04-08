# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for SearchTag."""
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


class SearchTagSchema(BaseModel):
    id: Annotated[str, Field(description='Primary key')]
    tenant_id: Annotated[str, Field(description='Tenant ID')]
    bu_id: Annotated[str, Field(description='Business Unit ID')]
    app_user_id: Annotated[str, Field(description='User who created the tag')]
    session_id: Annotated[str, Field(description='Search session where the tag was created')]
    crawled_profile_id: Annotated[str, Field(description='Tagged profile')]
    tag_name: Annotated[str, Field(description='Tag label')]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
