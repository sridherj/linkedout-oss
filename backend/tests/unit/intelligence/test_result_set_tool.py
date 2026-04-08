# SPDX-License-Identifier: Apache-2.0
"""Unit tests for in-memory result set tools."""
from linkedout.intelligence.tools.result_set_tool import compute_facets

# ── Test fixtures ────────────────────────────────────────────────────────

_SAMPLE_RESULTS = [
    {
        "crawled_profile_id": "cp_001",
        "full_name": "Alice Engineer",
        "current_position": "Senior Software Engineer",
        "current_company_name": "Google",
        "location_city": "Bangalore",
        "location_country": "India",
        "affinity_score": 85.0,
        "dunbar_tier": "active",
    },
    {
        "crawled_profile_id": "cp_002",
        "full_name": "Bob Manager",
        "current_position": "Engineering Manager",
        "current_company_name": "Meta",
        "location_city": "San Francisco",
        "location_country": "US",
        "affinity_score": 72.0,
        "dunbar_tier": "familiar",
    },
    {
        "crawled_profile_id": "cp_003",
        "full_name": "Carol Startup",
        "current_position": "CTO",
        "current_company_name": "TinyAI",
        "location_city": "Bangalore",
        "location_country": "India",
        "affinity_score": 91.0,
        "dunbar_tier": "inner_circle",
    },
    {
        "crawled_profile_id": "cp_004",
        "full_name": "Dave Director",
        "current_position": "Director of Engineering",
        "current_company_name": "Amazon",
        "location_city": "Seattle",
        "location_country": "US",
        "affinity_score": 65.0,
        "dunbar_tier": "acquaintance",
    },
    {
        "crawled_profile_id": "cp_005",
        "full_name": "Eve Founder",
        "current_position": "Founder & CEO",
        "current_company_name": "StartupXYZ",
        "location_city": "Bangalore",
        "location_country": "India",
        "affinity_score": 78.0,
        "dunbar_tier": "active",
    },
]


# ── compute_facets ───────────────────────────────────────────────────────

class TestComputeFacets:
    def test_returns_facet_groups(self):
        facets = compute_facets(_SAMPLE_RESULTS)
        group_names = [f["group"] for f in facets]
        assert "Location" in group_names
        assert "Dunbar Tier" in group_names

    def test_location_counts(self):
        facets = compute_facets(_SAMPLE_RESULTS)
        location = next(f for f in facets if f["group"] == "Location")
        bangalore = next(i for i in location["items"] if i["label"] == "Bangalore")
        assert bangalore["count"] == 3

    def test_empty_result_set(self):
        facets = compute_facets([])
        assert facets == []

    def test_seniority_facet_from_position(self):
        facets = compute_facets(_SAMPLE_RESULTS)
        seniority = next((f for f in facets if f["group"] == "Seniority"), None)
        if seniority:
            labels = [i["label"] for i in seniority["items"]]
            assert "Senior" in labels or "Manager" in labels or "Director" in labels
