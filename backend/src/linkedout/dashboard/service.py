# SPDX-License-Identifier: Apache-2.0
"""Dashboard service — orchestrates repository calls and assembles response."""
from collections import defaultdict

from linkedout.dashboard.repository import DashboardRepository
from linkedout.dashboard.schemas import AggregateCount, DashboardResponse, EnrichmentStatus

_SENIORITY_TIER_MAP: dict[str | None, str] = {
    "c_suite": "Executive",
    "founder": "Executive",
    "vp": "Executive",
    "director": "Director",
    "manager": "Manager",
    "lead": "Senior IC",
    "senior": "Senior IC",
    "mid": "IC",
    "junior": "IC",
    "intern": "IC",
    None: "IC",
}
_SENIORITY_TIER_ORDER = ["Executive", "Director", "Manager", "Senior IC", "IC"]


class DashboardService:
    def __init__(self, repository: DashboardRepository):
        self._repo = repository

    def get_dashboard(self, tenant_id: str, bu_id: str, app_user_id: str) -> DashboardResponse:
        total = self._repo.get_total_connections(tenant_id, bu_id, app_user_id)

        if total == 0:
            return DashboardResponse(
                enrichment_status=EnrichmentStatus(enriched=0, unenriched=0, total=0, enriched_pct=0.0),
                industry_breakdown=[],
                seniority_distribution=[],
                location_top=[],
                top_companies=[],
                affinity_tier_distribution=[],
                total_connections=0,
                network_sources=[],
            )

        enrichment_rows = self._repo.get_enrichment_status(tenant_id, bu_id, app_user_id)
        enriched = 0
        unenriched = 0
        for has_enriched, cnt in enrichment_rows:
            if has_enriched:
                enriched = cnt
            else:
                unenriched = cnt
        enrichment_total = enriched + unenriched
        enriched_pct = round(enriched / enrichment_total * 100, 1) if enrichment_total > 0 else 0.0

        return DashboardResponse(
            enrichment_status=EnrichmentStatus(
                enriched=enriched,
                unenriched=unenriched,
                total=enrichment_total,
                enriched_pct=enriched_pct,
            ),
            industry_breakdown=self._to_aggregates(
                self._repo.get_industry_breakdown(tenant_id, bu_id, app_user_id), total
            ),
            seniority_distribution=self._to_aggregates(
                self._bucket_seniority(
                    self._repo.get_seniority_distribution(tenant_id, bu_id, app_user_id)
                ),
                total,
            ),
            location_top=self._to_aggregates(
                self._repo.get_location_top(tenant_id, bu_id, app_user_id), total
            ),
            top_companies=self._to_aggregates(
                self._repo.get_top_companies(tenant_id, bu_id, app_user_id), total
            ),
            affinity_tier_distribution=self._to_aggregates(
                self._repo.get_affinity_tier_distribution(tenant_id, bu_id, app_user_id), total
            ),
            total_connections=total,
            network_sources=self._to_aggregates(
                self._repo.get_network_sources(tenant_id, bu_id, app_user_id), total
            ),
        )

    @staticmethod
    def _bucket_seniority(rows: list[tuple]) -> list[tuple]:
        """Collapse raw seniority levels into 5 display tiers in canonical order."""
        buckets: dict[str, int] = defaultdict(int)
        for label, cnt in rows:
            tier = _SENIORITY_TIER_MAP.get(label, "IC")
            buckets[tier] += cnt
        return [(tier, buckets[tier]) for tier in _SENIORITY_TIER_ORDER if buckets.get(tier)]

    @staticmethod
    def _to_aggregates(rows: list[tuple], total: int) -> list[AggregateCount]:
        return [
            AggregateCount(label=label, count=cnt, pct=round(cnt / total * 100, 1))
            for label, cnt in rows
        ]
