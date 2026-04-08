# SPDX-License-Identifier: Apache-2.0
"""Unit tests for result set tools (compute_facets)."""
from __future__ import annotations

import pytest

from linkedout.intelligence.tools.result_set_tool import compute_facets


@pytest.fixture()
def sample_result_set() -> list[dict]:
    return [
        {
            "crawled_profile_id": "cp_001",
            "full_name": "Alice Smith",
            "current_position": "Senior Engineer",
            "current_company_name": "Google",
            "location_city": "Bangalore",
            "dunbar_tier": "active",
            "affinity_score": 85.0,
            "similarity_score": 0.92,
            "connected_at": "2024-01-15",
        },
        {
            "crawled_profile_id": "cp_002",
            "full_name": "Bob Chen",
            "current_position": "Director of Engineering",
            "current_company_name": "Meta",
            "location_city": "San Francisco",
            "dunbar_tier": "inner_circle",
            "affinity_score": 92.0,
            "similarity_score": 0.88,
            "connected_at": "2023-06-01",
        },
        {
            "crawled_profile_id": "cp_003",
            "full_name": "Carol Jones",
            "current_position": "Staff Engineer",
            "current_company_name": "Stripe",
            "location_city": "Bangalore",
            "dunbar_tier": "familiar",
            "affinity_score": 45.0,
            "similarity_score": 0.75,
            "connected_at": "2025-03-20",
        },
        {
            "crawled_profile_id": "cp_004",
            "full_name": "Dave Patel",
            "current_position": "Founder & CEO",
            "current_company_name": "Acme AI",
            "location_city": "London",
            "dunbar_tier": "acquaintance",
            "affinity_score": 30.0,
            "similarity_score": 0.60,
            "connected_at": "2025-01-10",
        },
    ]


class TestComputeFacets:
    def test_produces_standard_facets(self, sample_result_set):
        facets = compute_facets(sample_result_set)
        group_names = {f["group"] for f in facets}
        assert "Dunbar Tier" in group_names
        assert "Location" in group_names
        assert "Company" in group_names

    def test_seniority_facet_inferred(self, sample_result_set):
        facets = compute_facets(sample_result_set)
        seniority = next((f for f in facets if f["group"] == "Seniority"), None)
        assert seniority is not None
        labels = {item["label"] for item in seniority["items"]}
        assert "Senior" in labels or "Staff" in labels

    def test_empty_result_set(self):
        facets = compute_facets([])
        assert facets == []

    def test_facet_items_capped_at_10(self):
        result_set = [
            {"location_city": f"City_{i}", "full_name": f"Person {i}"}
            for i in range(15)
        ]
        facets = compute_facets(result_set)
        location_facet = next((f for f in facets if f["group"] == "Location"), None)
        assert location_facet is not None
        assert len(location_facet["items"]) == 10
