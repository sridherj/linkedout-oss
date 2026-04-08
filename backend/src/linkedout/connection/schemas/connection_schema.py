# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for Connection."""
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DunbarTier(StrEnum):
    INNER_CIRCLE = 'inner_circle'
    ACTIVE = 'active'
    FAMILIAR = 'familiar'
    ACQUAINTANCE = 'acquaintance'


class ConnectionSchema(BaseModel):
    id: Annotated[str, Field(description='Unique Connection ID')]
    tenant_id: Annotated[str, Field(description='Tenant ID')]
    bu_id: Annotated[str, Field(description='Business Unit ID')]
    app_user_id: Annotated[str, Field(description='User who owns this connection')]
    crawled_profile_id: Annotated[str, Field(description='Profile representing the connected person')]
    connected_at: Annotated[Optional[date], Field(default=None, description='When the connection was established')]
    emails: Annotated[Optional[str], Field(default=None, description='Comma-separated email addresses')]
    phones: Annotated[Optional[str], Field(default=None, description='Comma-separated phone numbers')]
    notes: Annotated[Optional[str], Field(default=None, description='Personal notes about this connection')]
    tags: Annotated[Optional[str], Field(default=None, description='Comma-separated tags')]
    sources: Annotated[Optional[List[str]], Field(default=None, description='Sources of connection')]
    source_details: Annotated[Optional[str], Field(default=None, description='Raw JSON data from the source')]
    affinity_score: Annotated[Optional[float], Field(default=None, description='Calculated affinity score')]
    dunbar_tier: Annotated[Optional[str], Field(default=None, description='Assigned Dunbar tier')]
    affinity_source_count: Annotated[float, Field(default=0, description='Number of interaction sources factored')]
    affinity_recency: Annotated[float, Field(default=0, description='Recency dimension')]
    affinity_career_overlap: Annotated[float, Field(default=0, description='Career overlap dimension')]
    affinity_mutual_connections: Annotated[float, Field(default=0, description='Mutual connections dimension')]
    affinity_computed_at: Annotated[Optional[datetime], Field(default=None, description='When affinity was computed')]
    affinity_version: Annotated[int, Field(default=0, description='Version of affinity algorithm')]
    created_at: Annotated[datetime, Field(description='Creation time')]
    updated_at: Annotated[datetime, Field(description='Update time')]

    model_config = ConfigDict(from_attributes=True)
