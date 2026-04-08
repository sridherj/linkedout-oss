# SPDX-License-Identifier: Apache-2.0
"""Schemas for enrichment pipeline endpoints."""
from pydantic import BaseModel, Field


class EnrichTriggerRequest(BaseModel):
    """Request body for the enrichment trigger endpoint."""
    profile_ids: list[str] = Field(default_factory=list, description='CrawledProfile IDs to enrich directly')
    connection_ids: list[str] = Field(default_factory=list, description='Connection IDs — resolve to linked profiles')
    all_unenriched: bool = Field(default=False, description='Enrich all profiles with has_enriched_data=False')
    max_count: int = Field(default=100, ge=1, le=1000, description='Max profiles to enqueue')
    enrichment_mode: str = Field(default='platform', pattern='^(platform|byok)$')
    app_user_id: str = Field(..., description='User triggering the enrichment')


class EnrichTriggerResponse(BaseModel):
    """Response from enrichment trigger endpoint."""
    queued: int = 0
    cached: int = 0
    skipped_no_url: int = 0
    estimated_cost_usd: float = 0.0
