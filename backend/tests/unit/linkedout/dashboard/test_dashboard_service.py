# SPDX-License-Identifier: Apache-2.0
"""Unit tests for DashboardService with mocked repository."""
from unittest.mock import MagicMock

import pytest

from linkedout.dashboard.repository import DashboardRepository
from linkedout.dashboard.schemas import DashboardResponse, EnrichmentStatus
from linkedout.dashboard.service import DashboardService

TENANT = "t1"
BU = "b1"
USER = "u1"


@pytest.fixture()
def mock_repo():
    return MagicMock(spec=DashboardRepository)


@pytest.fixture()
def service(mock_repo):
    return DashboardService(mock_repo)


class TestCorrectAssembly:
    """Service assembles DashboardResponse from all 7 repository sections."""

    def test_all_sections_populated(self, service, mock_repo):
        mock_repo.get_total_connections.return_value = 20
        mock_repo.get_enrichment_status.return_value = [(True, 15), (False, 5)]
        mock_repo.get_industry_breakdown.return_value = [("Tech", 12), ("Finance", 8)]
        mock_repo.get_seniority_distribution.return_value = [("senior", 10), ("mid", 10)]
        mock_repo.get_location_top.return_value = [("SF", 14), ("NYC", 6)]
        mock_repo.get_top_companies.return_value = [("Google", 8), ("Stripe", 12)]
        mock_repo.get_affinity_tier_distribution.return_value = [("Tier1", 5), ("Tier2", 15)]
        mock_repo.get_network_sources.return_value = [("linkedin", 20), ("gmail", 10)]

        result = service.get_dashboard(TENANT, BU, USER)

        assert isinstance(result, DashboardResponse)
        assert result.total_connections == 20
        assert result.enrichment_status.enriched == 15
        assert result.enrichment_status.unenriched == 5
        assert len(result.industry_breakdown) == 2
        assert len(result.seniority_distribution) == 2
        assert len(result.location_top) == 2
        assert len(result.top_companies) == 2
        assert len(result.affinity_tier_distribution) == 2
        assert len(result.network_sources) == 2


class TestEnrichmentCalculation:
    """Enrichment percentage calculation."""

    def test_enrichment_pct(self, service, mock_repo):
        mock_repo.get_total_connections.return_value = 15
        mock_repo.get_enrichment_status.return_value = [(True, 10), (False, 5)]
        mock_repo.get_industry_breakdown.return_value = []
        mock_repo.get_seniority_distribution.return_value = []
        mock_repo.get_location_top.return_value = []
        mock_repo.get_top_companies.return_value = []
        mock_repo.get_affinity_tier_distribution.return_value = []
        mock_repo.get_network_sources.return_value = []

        result = service.get_dashboard(TENANT, BU, USER)

        assert result.enrichment_status.enriched == 10
        assert result.enrichment_status.unenriched == 5
        assert result.enrichment_status.total == 15
        assert result.enrichment_status.enriched_pct == 66.7


class TestTopNSorting:
    """Aggregates should preserve repo ordering (count desc)."""

    def test_industry_sorted_desc(self, service, mock_repo):
        mock_repo.get_total_connections.return_value = 30
        mock_repo.get_enrichment_status.return_value = [(True, 30)]
        mock_repo.get_industry_breakdown.return_value = [("Tech", 20), ("Finance", 7), ("Health", 3)]
        mock_repo.get_seniority_distribution.return_value = []
        mock_repo.get_location_top.return_value = []
        mock_repo.get_top_companies.return_value = []
        mock_repo.get_affinity_tier_distribution.return_value = []
        mock_repo.get_network_sources.return_value = []

        result = service.get_dashboard(TENANT, BU, USER)

        labels = [a.label for a in result.industry_breakdown]
        assert labels == ["Tech", "Finance", "Health"]
        counts = [a.count for a in result.industry_breakdown]
        assert counts == [20, 7, 3]


class TestPercentageCalculation:
    """Each AggregateCount.pct should be relative to total_connections."""

    def test_pct_relative_to_total(self, service, mock_repo):
        mock_repo.get_total_connections.return_value = 50
        mock_repo.get_enrichment_status.return_value = [(True, 50)]
        mock_repo.get_industry_breakdown.return_value = [("Tech", 25), ("Finance", 25)]
        mock_repo.get_seniority_distribution.return_value = []
        mock_repo.get_location_top.return_value = []
        mock_repo.get_top_companies.return_value = []
        mock_repo.get_affinity_tier_distribution.return_value = []
        mock_repo.get_network_sources.return_value = []

        result = service.get_dashboard(TENANT, BU, USER)

        for agg in result.industry_breakdown:
            assert agg.pct == 50.0


class TestEmptyConnections:
    """When total=0, service returns all zeros and empty lists."""

    def test_empty_state(self, service, mock_repo):
        mock_repo.get_total_connections.return_value = 0

        result = service.get_dashboard(TENANT, BU, USER)

        assert result.total_connections == 0
        assert result.enrichment_status == EnrichmentStatus(
            enriched=0, unenriched=0, total=0, enriched_pct=0.0
        )
        assert result.industry_breakdown == []
        assert result.seniority_distribution == []
        assert result.location_top == []
        assert result.top_companies == []
        assert result.affinity_tier_distribution == []
        assert result.network_sources == []


class TestSeniorityBucketing:
    """Service collapses raw seniority levels into 5 display tiers."""

    def _make_result(self, service, mock_repo, seniority_rows):
        mock_repo.get_total_connections.return_value = sum(cnt for _, cnt in seniority_rows)
        mock_repo.get_enrichment_status.return_value = [(True, mock_repo.get_total_connections.return_value)]
        mock_repo.get_industry_breakdown.return_value = []
        mock_repo.get_seniority_distribution.return_value = seniority_rows
        mock_repo.get_location_top.return_value = []
        mock_repo.get_top_companies.return_value = []
        mock_repo.get_affinity_tier_distribution.return_value = []
        mock_repo.get_network_sources.return_value = []
        return service.get_dashboard(TENANT, BU, USER)

    def test_null_maps_to_ic(self, service, mock_repo):
        result = self._make_result(service, mock_repo, [(None, 6), ("senior", 4)])
        labels = [a.label for a in result.seniority_distribution]
        assert labels == ["Senior IC", "IC"]

    def test_multiple_levels_merge_into_same_tier(self, service, mock_repo):
        result = self._make_result(service, mock_repo, [("c_suite", 2), ("founder", 1), ("vp", 3)])
        labels = [a.label for a in result.seniority_distribution]
        assert labels == ["Executive"]
        assert result.seniority_distribution[0].count == 6

    def test_canonical_order(self, service, mock_repo):
        result = self._make_result(service, mock_repo, [
            ("intern", 1), ("c_suite", 2), ("manager", 3), ("director", 4), ("lead", 5),
        ])
        labels = [a.label for a in result.seniority_distribution]
        assert labels == ["Executive", "Director", "Manager", "Senior IC", "IC"]

    def test_unknown_db_value_maps_to_ic(self, service, mock_repo):
        result = self._make_result(service, mock_repo, [("something_new", 5)])
        labels = [a.label for a in result.seniority_distribution]
        assert labels == ["IC"]

    def test_empty_input(self, service, mock_repo):
        result = self._make_result(service, mock_repo, [])
        # total=0 triggers early return
        assert result.seniority_distribution == []
