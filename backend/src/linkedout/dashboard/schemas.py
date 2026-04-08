# SPDX-License-Identifier: Apache-2.0
"""Response schemas for the network dashboard aggregation endpoint."""
from pydantic import BaseModel


class AggregateCount(BaseModel):
    label: str
    count: int
    pct: float  # percentage of total, 0-100


class EnrichmentStatus(BaseModel):
    enriched: int
    unenriched: int
    total: int
    enriched_pct: float  # 0-100


class DashboardResponse(BaseModel):
    enrichment_status: EnrichmentStatus
    industry_breakdown: list[AggregateCount]
    seniority_distribution: list[AggregateCount]
    location_top: list[AggregateCount]
    top_companies: list[AggregateCount]
    affinity_tier_distribution: list[AggregateCount]
    total_connections: int
    network_sources: list[AggregateCount]
