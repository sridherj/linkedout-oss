# SPDX-License-Identifier: Apache-2.0
"""Schemas for AppUserTenantRole."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AppUserTenantRoleSchema(BaseModel):
    id: str
    app_user_id: str
    tenant_id: str
    role: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
