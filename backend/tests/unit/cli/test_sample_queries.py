# SPDX-License-Identifier: Apache-2.0
"""Unit tests for demo sample queries and demo profile formatting."""
from __future__ import annotations

from linkedout.demo.sample_queries import (
    DEMO_USER_PROFILE_DESCRIPTION,
    SAMPLE_QUERIES,
    format_demo_profile,
    format_sample_queries,
)


class TestSampleQueriesContent:

    def test_three_sample_queries(self):
        """There should be exactly 3 curated sample queries."""
        assert len(SAMPLE_QUERIES) == 3

    def test_covers_all_three_pillars(self):
        """Queries should cover search, affinity, and agent categories."""
        categories = {q["category"] for q in SAMPLE_QUERIES}
        assert categories == {"search", "affinity", "agent"}

    def test_each_query_has_required_fields(self):
        required = {"category", "title", "query", "explanation", "followups"}
        for q in SAMPLE_QUERIES:
            assert required.issubset(q.keys()), f"Missing fields in query: {q.get('title', '?')}"

    def test_each_query_has_followups(self):
        for q in SAMPLE_QUERIES:
            assert len(q["followups"]) > 0, f"No followups for {q['title']}"

    def test_queries_are_non_empty_strings(self):
        for q in SAMPLE_QUERIES:
            assert isinstance(q["query"], str) and len(q["query"]) > 10


class TestDemoProfileDescription:

    def test_profile_describes_founder_cto(self):
        assert "Founder/CTO" in DEMO_USER_PROFILE_DESCRIPTION

    def test_profile_mentions_bengaluru(self):
        assert "Bengaluru" in DEMO_USER_PROFILE_DESCRIPTION

    def test_profile_mentions_affinity(self):
        assert "affinity" in DEMO_USER_PROFILE_DESCRIPTION.lower()


class TestFormatDemoProfile:

    def test_returns_string(self):
        result = format_demo_profile()
        assert isinstance(result, str)

    def test_contains_profile_header(self):
        result = format_demo_profile()
        assert "Demo Profile" in result

    def test_contains_profile_content(self):
        result = format_demo_profile()
        assert "Founder/CTO" in result


class TestFormatSampleQueries:

    def test_returns_string(self):
        result = format_sample_queries()
        assert isinstance(result, str)

    def test_contains_all_query_titles(self):
        result = format_sample_queries()
        for q in SAMPLE_QUERIES:
            assert q["title"] in result

    def test_contains_demo_help_tip(self):
        result = format_sample_queries()
        assert "demo-help" in result

    def test_numbered_queries(self):
        result = format_sample_queries()
        assert "1." in result
        assert "2." in result
        assert "3." in result
