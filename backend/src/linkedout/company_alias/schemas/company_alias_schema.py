# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for CompanyAlias."""
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


class CompanyAliasSchema(BaseModel):
    id: Annotated[str, Field(description='Unique alias ID')]
    alias_name: Annotated[str, Field(description='Alternative company name')]
    company_id: Annotated[str, Field(description='Parent company ID')]
    source: Annotated[Optional[str], Field(default=None, description='Source of alias data')]
    created_at: Annotated[datetime, Field(description='Creation time')]
    updated_at: Annotated[datetime, Field(description='Update time')]

    model_config = ConfigDict(from_attributes=True)
