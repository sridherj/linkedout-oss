# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for RoleAlias."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RoleAliasSchema(BaseModel):
    id: str
    alias_title: str
    canonical_title: str
    seniority_level: Optional[str] = None
    function_area: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
