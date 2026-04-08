# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for EnrichmentEvent."""
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


class EnrichmentEventType(StrEnum):
    CRAWLED = 'crawled'
    CACHE_HIT = 'cache_hit'
    FAILED = 'failed'
    RETRY = 'retry'


class EnrichmentMode(StrEnum):
    PLATFORM = 'platform'
    BYOK = 'byok'


class EnrichmentEventSchema(BaseModel):
    id: Annotated[str, Field(description='Unique ID')]
    tenant_id: Annotated[str, Field(description='Tenant ID')]
    bu_id: Annotated[str, Field(description='BU ID')]
    app_user_id: Annotated[str, Field(description='User who initiated the enrichment')]
    crawled_profile_id: Annotated[str, Field(description='Profile this enrichment targets')]
    event_type: Annotated[str, Field(description='Type of enrichment event')]
    enrichment_mode: Annotated[str, Field(description='Mode of enrichment')]
    crawler_name: Annotated[Optional[str], Field(default=None, description='Name of the crawler used')]
    cost_estimate_usd: Annotated[float, Field(default=0, description='Estimated cost in USD')]
    crawler_run_id: Annotated[Optional[str], Field(default=None, description='ID of the crawler run')]
    created_at: Annotated[datetime, Field(description='Creation time')]
    updated_at: Annotated[datetime, Field(description='Update time')]

    model_config = ConfigDict(from_attributes=True)
