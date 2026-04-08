# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the introduction path finder tool."""
from unittest.mock import MagicMock

from linkedout.intelligence.tools.intro_tool import find_intro_paths


class TestFindIntroPaths:
    def _mock_session(
        self,
        tier1_rows=None,
        tier2_rows=None,
        tier3_rows=None,
        tier4_rows=None,
        tier5_rows=None,
    ):
        session = MagicMock()
        call_count = [0]
        tier_data = [
            tier1_rows or [],
            tier2_rows or [],
            tier3_rows or [],
            tier4_rows or [],
            tier5_rows or [],
        ]

        def mock_execute(query, params=None):
            result = MagicMock()
            idx = min(call_count[0], len(tier_data) - 1)
            result.fetchall.return_value = tier_data[idx]
            call_count[0] += 1
            return result

        session.execute.side_effect = mock_execute
        return session

    def test_empty_target_returns_error(self):
        session = MagicMock()
        result = find_intro_paths("", session)
        assert "error" in result

    def test_whitespace_target_returns_error(self):
        session = MagicMock()
        result = find_intro_paths("   ", session)
        assert "error" in result

    def test_returns_tier1_direct_connections(self):
        tier1_rows = [
            ("cp_1", "Alice", "SDE", "Google", 85.0, "active"),
            ("cp_2", "Bob", "PM", "Google", 70.0, "familiar"),
        ]
        session = self._mock_session(tier1_rows=tier1_rows)
        result = find_intro_paths("Google", session)
        assert result["target"] == "Google"
        assert result["tier1_count"] == 2
        assert all(p["tier"] == 1 for p in result["paths"] if p["tier"] == 1)
        assert result["paths"][0]["path_type"] == "direct"
        assert result["paths"][0]["intermediary"] == "Alice"

    def test_returns_tier2_alumni(self):
        tier2_rows = [
            ("cp_3", "Charlie", "Manager", "Meta", "SDE", "Google", 60.0, "acquaintance"),
        ]
        session = self._mock_session(tier2_rows=tier2_rows)
        result = find_intro_paths("Google", session)
        assert result["tier2_count"] == 1
        alumni = [p for p in result["paths"] if p["tier"] == 2]
        assert len(alumni) == 1
        assert alumni[0]["path_type"] == "alumni"
        assert alumni[0]["past_company"] == "Google"

    def test_no_paths_found(self):
        session = self._mock_session()
        result = find_intro_paths("NonexistentCorp", session)
        assert result["paths"] == []
        assert result["tier1_count"] == 0
        assert result["tier2_count"] == 0
        assert result["tier3_count"] == 0
        assert result["tier4_count"] == 0
        assert result["tier5_count"] == 0

    def test_returns_structured_json(self):
        tier1_rows = [("cp_1", "Alice", "SDE", "Stripe", 90.0, "inner_circle")]
        session = self._mock_session(tier1_rows=tier1_rows)
        result = find_intro_paths("Stripe", session)
        assert "target" in result
        assert "paths" in result
        for key in ("tier1_count", "tier2_count", "tier3_count", "tier4_count", "tier5_count"):
            assert key in result
        path = result["paths"][0]
        assert "tier" in path
        assert "path_type" in path
        assert "profile_id" in path
        assert "intermediary" in path
        assert "affinity_score" in path

    def test_tier3_headline_mentions(self):
        """Tier 3: profiles mentioning target in headline but NOT employed there."""
        tier3_rows = [
            ("cp_10", "Dana", "Google Cloud Partner", "Consultant", "Acme Corp", 75.0, "familiar"),
            ("cp_11", "Eve", "Ex-Google, now freelance", "Freelancer", None, 50.0, "acquaintance"),
        ]
        session = self._mock_session(tier3_rows=tier3_rows)
        result = find_intro_paths("Google", session)
        assert result["tier3_count"] == 2
        headline_paths = [p for p in result["paths"] if p["tier"] == 3]
        assert len(headline_paths) == 2
        assert headline_paths[0]["path_type"] == "headline_mention"
        assert headline_paths[0]["intermediary"] == "Dana"
        assert headline_paths[0]["headline"] == "Google Cloud Partner"
        # Ensure these are NOT tier 1 (direct employees)
        assert all(p["path_type"] != "direct" for p in headline_paths)

    def test_tier4_shared_company_warm_paths(self):
        """Tier 4: connections who worked at same prior companies as target employees."""
        tier4_rows = [
            ("cp_20", "Frank", "SDE", "Amazon", 80.0, "active", "Microsoft", "George"),
        ]
        session = self._mock_session(tier4_rows=tier4_rows)
        result = find_intro_paths("Stripe", session)
        assert result["tier4_count"] == 1
        shared = [p for p in result["paths"] if p["tier"] == 4]
        assert len(shared) == 1
        assert shared[0]["path_type"] == "shared_company"
        assert shared[0]["shared_company"] == "Microsoft"
        assert shared[0]["target_person"] == "George"
        assert shared[0]["intermediary"] == "Frank"

    def test_tier5_investor_connections(self):
        """Tier 5: connections at firms that invested in target company."""
        tier5_rows = [
            ("cp_30", "Hank", "Partner", "Sequoia Capital", 90.0, "inner_circle"),
        ]
        session = self._mock_session(tier5_rows=tier5_rows)
        result = find_intro_paths("Stripe", session)
        assert result["tier5_count"] == 1
        investor_paths = [p for p in result["paths"] if p["tier"] == 5]
        assert len(investor_paths) == 1
        assert investor_paths[0]["path_type"] == "investor"
        assert investor_paths[0]["intermediary"] == "Hank"
        assert investor_paths[0]["company"] == "Sequoia Capital"

    def test_empty_tier_returns_zero(self):
        """Each tier returns count of 0 without error when no rows match."""
        # Only tier 1 has data, all others empty
        tier1_rows = [("cp_1", "Alice", "SDE", "Stripe", 90.0, "active")]
        session = self._mock_session(tier1_rows=tier1_rows)
        result = find_intro_paths("Stripe", session)
        assert result["tier1_count"] == 1
        assert result["tier2_count"] == 0
        assert result["tier3_count"] == 0
        assert result["tier4_count"] == 0
        assert result["tier5_count"] == 0

    def test_all_tiers_combined(self):
        """All 5 tiers return results simultaneously."""
        session = self._mock_session(
            tier1_rows=[("cp_1", "A", "SDE", "Stripe", 90.0, "active")],
            tier2_rows=[("cp_2", "B", "PM", "Meta", "SDE", "Stripe", 80.0, "familiar")],
            tier3_rows=[("cp_3", "C", "Stripe advisor", "Advisor", "Consulting", 70.0, "acquaintance")],
            tier4_rows=[("cp_4", "D", "Eng", "Google", 60.0, "familiar", "Acme", "E")],
            tier5_rows=[("cp_5", "F", "Partner", "a16z", 50.0, "acquaintance")],
        )
        result = find_intro_paths("Stripe", session)
        assert result["tier1_count"] == 1
        assert result["tier2_count"] == 1
        assert result["tier3_count"] == 1
        assert result["tier4_count"] == 1
        assert result["tier5_count"] == 1
        assert len(result["paths"]) == 5
