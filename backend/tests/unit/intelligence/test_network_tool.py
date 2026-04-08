# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the network statistics tool."""
from unittest.mock import MagicMock, call

import pytest

from linkedout.intelligence.tools.network_tool import get_network_stats


class TestGetNetworkStats:
    def _mock_session(
        self,
        total=100,
        companies=None,
        industries=None,
        seniority=None,
        locations=None,
    ):
        session = MagicMock()
        call_count = [0]

        if companies is None:
            companies = [("Google", 15), ("Meta", 10)]
        if industries is None:
            industries = [("Internet", 20), ("Software", 15)]
        if seniority is None:
            seniority = [("senior", 30), ("mid", 25)]
        if locations is None:
            locations = [("Bangalore", "India", 40), ("San Francisco", "US", 20)]

        def mock_execute(query, params=None):
            result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # Total connections
                result.scalar.return_value = total
            elif call_count[0] == 2:
                result.fetchall.return_value = companies
            elif call_count[0] == 3:
                result.fetchall.return_value = industries
            elif call_count[0] == 4:
                result.fetchall.return_value = seniority
            elif call_count[0] == 5:
                result.fetchall.return_value = locations
            return result

        session.execute.side_effect = mock_execute
        return session

    def test_returns_total_connections(self):
        session = self._mock_session(total=500)
        result = get_network_stats(session)
        assert result["total_connections"] == 500

    def test_returns_top_companies(self):
        session = self._mock_session(companies=[("Google", 15), ("Meta", 10)])
        result = get_network_stats(session)
        assert len(result["top_companies"]) == 2
        assert result["top_companies"][0]["name"] == "Google"
        assert result["top_companies"][0]["count"] == 15

    def test_returns_top_industries(self):
        session = self._mock_session(industries=[("Internet", 20)])
        result = get_network_stats(session)
        assert len(result["top_industries"]) >= 1
        assert result["top_industries"][0]["industry"] == "Internet"

    def test_returns_seniority_distribution(self):
        session = self._mock_session(seniority=[("senior", 30), ("mid", 25)])
        result = get_network_stats(session)
        assert len(result["seniority_distribution"]) == 2
        levels = [s["level"] for s in result["seniority_distribution"]]
        assert "senior" in levels

    def test_returns_top_locations(self):
        session = self._mock_session(locations=[("Bangalore", "India", 40)])
        result = get_network_stats(session)
        assert len(result["top_locations"]) >= 1
        loc = result["top_locations"][0]
        assert loc["city"] == "Bangalore"
        assert loc["country"] == "India"
        assert loc["count"] == 40

    def test_returns_structured_json(self):
        session = self._mock_session()
        result = get_network_stats(session)
        assert "total_connections" in result
        assert "top_companies" in result
        assert "top_industries" in result
        assert "seniority_distribution" in result
        assert "top_locations" in result
        assert isinstance(result["top_companies"], list)
        assert isinstance(result["top_industries"], list)

    def test_handles_zero_connections(self):
        session = self._mock_session(
            total=0, companies=[], industries=[], seniority=[], locations=[],
        )
        result = get_network_stats(session)
        assert result["total_connections"] == 0
        assert result["top_companies"] == []
