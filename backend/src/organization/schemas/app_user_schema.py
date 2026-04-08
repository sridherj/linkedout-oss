# SPDX-License-Identifier: Apache-2.0
"""Schemas for AppUser."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AppUserSchema(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    auth_provider_id: Optional[str] = None
    own_crawled_profile_id: Optional[str] = None
    network_preferences: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
