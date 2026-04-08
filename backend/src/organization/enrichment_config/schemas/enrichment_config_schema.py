# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for EnrichmentConfig."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class EnrichmentConfigSchema(BaseModel):
    id: str
    app_user_id: str
    enrichment_mode: str
    apify_key_encrypted: Optional[str] = None
    apify_key_hint: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
