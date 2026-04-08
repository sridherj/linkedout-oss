# SPDX-License-Identifier: Apache-2.0
"""Unit tests for WhyThisPersonExplainer."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from linkedout.intelligence.contracts import (
    HighlightedAttribute,
    MatchStrength,
    ProfileExplanation,
    SearchResultItem,
)
from linkedout.intelligence.explainer.why_this_person import (
    BATCH_SIZE,
    WhyThisPersonExplainer,
    _format_profile,
    _parse_explanations,
)


def _make_item(**overrides) -> SearchResultItem:
    defaults = {
        "connection_id": "conn_001",
        "crawled_profile_id": "cp_001",
        "full_name": "Alice Smith",
        "headline": "Senior Engineer at Acme",
        "current_position": "Senior Engineer",
        "current_company_name": "Acme Corp",
        "location_city": "San Francisco",
        "location_country": "US",
    }
    defaults.update(overrides)
    return SearchResultItem(**defaults)


class TestFormatProfile:
    def test_basic_formatting(self):
        item = _make_item()
        result = _format_profile(item)
        assert "## Profile: conn_001" in result
        assert "Name: Alice Smith" in result
        assert "Current: Senior Engineer at Acme Corp" in result
        assert "Location: San Francisco, US" in result

    def test_minimal_fields(self):
        item = _make_item(
            current_position=None,
            current_company_name=None,
            location_city=None,
            headline=None,
        )
        result = _format_profile(item)
        assert "## Profile: conn_001" in result
        assert "Name: Alice Smith" in result
        assert "Current:" not in result
        assert "Location:" not in result

    def test_with_enrichment(self):
        item = _make_item(affinity_score=0.85, dunbar_tier="inner_circle")
        enrichment = {
            "experiences": [
                {"position": "SWE", "company": "Google", "start": "2020-01-01", "end": None,
                 "current": True, "company_industry": "Tech", "company_size_tier": "Large"},
                {"position": "Junior Dev", "company": "Startup", "start": "2018-01-01", "end": "2019-12-31",
                 "current": False, "company_industry": "AI", "company_size_tier": "Small"},
            ],
            "education": [
                {"school": "MIT", "degree": "BS", "field": "CS", "end_year": 2018},
            ],
            "skills": ["Python", "Go", "Kubernetes"],
            "affinity": {"recency": 8.5, "career_overlap": 6.2, "mutual_connections": 3.1},
            "current_company_meta": {"industry": "Tech", "size_tier": "Large"},
        }
        result = _format_profile(item, enrichment)
        assert "Career:" in result
        assert "Google" in result
        assert "Education:" in result
        assert "MIT" in result
        assert "Skills:" in result
        assert "Python" in result
        assert "Affinity=0.85" in result
        assert "Tier=inner_circle" in result
        assert "Recency=8.5" in result
        assert "(Tech, Large)" in result  # company metadata on current role

    def test_network_signals_without_enrichment(self):
        item = _make_item(affinity_score=0.72, dunbar_tier="active")
        result = _format_profile(item)
        assert "Affinity=0.72" in result
        assert "Tier=active" in result


class TestParseExplanations:
    def test_parses_valid_json(self):
        raw = json.dumps([
            {
                "connection_id": "conn_001",
                "match_strength": "strong",
                "explanation": "Strong match due to Python background at Google.",
                "highlighted_attributes": [
                    {"text": "8yr Python", "color_tier": 0},
                    {"text": "Ex-Google", "color_tier": 1},
                ],
            },
            {
                "connection_id": "conn_002",
                "match_strength": "weak",
                "explanation": "Located in SF with relevant skills.",
                "highlighted_attributes": [
                    {"text": "SF based", "color_tier": 0},
                ],
            },
        ])
        valid_ids = {"conn_001", "conn_002"}
        result = _parse_explanations(raw, valid_ids)

        assert len(result) == 2
        assert isinstance(result["conn_001"], ProfileExplanation)
        assert "Python" in result["conn_001"].explanation
        assert result["conn_001"].match_strength == MatchStrength.STRONG
        assert len(result["conn_001"].highlighted_attributes) == 2
        assert result["conn_001"].highlighted_attributes[0].text == "8yr Python"
        assert result["conn_001"].highlighted_attributes[0].color_tier == 0
        assert result["conn_002"].match_strength == MatchStrength.WEAK

    def test_match_strength_defaults_to_partial(self):
        raw = json.dumps([{
            "connection_id": "conn_001",
            "explanation": "Match.",
            "highlighted_attributes": [],
        }])
        result = _parse_explanations(raw, {"conn_001"})
        assert result["conn_001"].match_strength == MatchStrength.PARTIAL

    def test_invalid_match_strength_defaults_to_partial(self):
        raw = json.dumps([{
            "connection_id": "conn_001",
            "match_strength": "excellent",
            "explanation": "Match.",
            "highlighted_attributes": [],
        }])
        result = _parse_explanations(raw, {"conn_001"})
        assert result["conn_001"].match_strength == MatchStrength.PARTIAL

    def test_parses_json_with_markdown_fences(self):
        inner = json.dumps([{
            "connection_id": "conn_001",
            "explanation": "Match.",
            "highlighted_attributes": [],
        }])
        raw = f"```json\n{inner}\n```"
        result = _parse_explanations(raw, {"conn_001"})
        assert "conn_001" in result

    def test_ignores_unknown_ids(self):
        raw = json.dumps([
            {"connection_id": "conn_001", "explanation": "Good.", "highlighted_attributes": []},
            {"connection_id": "conn_999", "explanation": "Unknown.", "highlighted_attributes": []},
        ])
        result = _parse_explanations(raw, {"conn_001"})
        assert "conn_001" in result
        assert "conn_999" not in result

    def test_truncates_highlights_to_3(self):
        raw = json.dumps([{
            "connection_id": "conn_001",
            "explanation": "Match.",
            "highlighted_attributes": [
                {"text": "a", "color_tier": 0},
                {"text": "b", "color_tier": 1},
                {"text": "c", "color_tier": 2},
                {"text": "d", "color_tier": 0},  # should be dropped
            ],
        }])
        result = _parse_explanations(raw, {"conn_001"})
        assert len(result["conn_001"].highlighted_attributes) == 3

    def test_clamps_invalid_color_tier(self):
        raw = json.dumps([{
            "connection_id": "conn_001",
            "explanation": "Match.",
            "highlighted_attributes": [
                {"text": "chip", "color_tier": 5},  # invalid, should default to 2
            ],
        }])
        result = _parse_explanations(raw, {"conn_001"})
        assert result["conn_001"].highlighted_attributes[0].color_tier == 2

    def test_truncates_long_chip_text(self):
        raw = json.dumps([{
            "connection_id": "conn_001",
            "explanation": "Match.",
            "highlighted_attributes": [
                {"text": "A" * 50, "color_tier": 0},  # 50 chars, should be truncated to 25
            ],
        }])
        result = _parse_explanations(raw, {"conn_001"})
        assert len(result["conn_001"].highlighted_attributes[0].text) == 25

    def test_falls_back_to_text_parsing(self):
        raw = "conn_001: Great match because of Python experience\nconn_002: Works at target company"
        valid_ids = {"conn_001", "conn_002"}
        result = _parse_explanations(raw, valid_ids)
        assert len(result) == 2
        assert isinstance(result["conn_001"], ProfileExplanation)
        assert "Python" in result["conn_001"].explanation
        assert result["conn_001"].highlighted_attributes == []
        assert result["conn_001"].match_strength == MatchStrength.PARTIAL  # default for text fallback

    def test_handles_empty_input(self):
        assert _parse_explanations("", set()) == {}
        assert _parse_explanations("\n\n", {"conn_001"}) == {}

    def test_fallback_ignores_malformed_lines(self):
        raw = "No colon here\nconn_001: Valid line\nJust random text"
        result = _parse_explanations(raw, {"conn_001"})
        assert len(result) == 1
        assert result["conn_001"].explanation == "Valid line"


class TestWhyThisPersonExplainer:
    @patch("linkedout.intelligence.explainer.why_this_person.WhyThisPersonExplainer._create_llm_client")
    def test_explain_returns_structured_explanations(self, mock_create_client):
        mock_client = MagicMock()
        mock_client.call_llm.return_value = json.dumps([
            {
                "connection_id": "conn_001",
                "match_strength": "strong",
                "explanation": "Strong Python background at Google.",
                "highlighted_attributes": [{"text": "Python expert", "color_tier": 0}],
            },
            {
                "connection_id": "conn_002",
                "match_strength": "partial",
                "explanation": "Located in SF.",
                "highlighted_attributes": [{"text": "SF based", "color_tier": 0}],
            },
        ])
        mock_create_client.return_value = mock_client

        explainer = WhyThisPersonExplainer()
        results = [
            _make_item(connection_id="conn_001"),
            _make_item(connection_id="conn_002", full_name="Bob Jones"),
        ]
        explanations = explainer.explain("Python engineers in SF", results)

        assert isinstance(explanations["conn_001"], ProfileExplanation)
        assert "Python" in explanations["conn_001"].explanation
        assert len(explanations["conn_001"].highlighted_attributes) == 1
        mock_client.call_llm.assert_called_once()

    @patch("linkedout.intelligence.explainer.why_this_person.WhyThisPersonExplainer._create_llm_client")
    def test_explain_empty_results(self, mock_create_client):
        explainer = WhyThisPersonExplainer()
        assert explainer.explain("any query", []) == {}
        mock_create_client.assert_not_called()

    @patch("linkedout.intelligence.explainer.why_this_person.WhyThisPersonExplainer._create_llm_client")
    def test_explain_handles_llm_error(self, mock_create_client):
        mock_client = MagicMock()
        mock_client.call_llm.side_effect = RuntimeError("LLM unavailable")
        mock_create_client.return_value = mock_client

        explainer = WhyThisPersonExplainer()
        results = [_make_item()]
        assert explainer.explain("test query", results) == {}

    @patch("linkedout.intelligence.explainer.why_this_person.WhyThisPersonExplainer._create_llm_client")
    def test_batching_splits_large_result_sets(self, mock_create_client):
        """Verify that results are split into batches of BATCH_SIZE."""
        mock_client = MagicMock()
        # Return valid JSON for each batch call
        def make_response(msg):
            # Parse which connection_ids are in this batch from the prompt
            import re
            prompt_text = msg.get_messages()[0]["content"]
            ids = re.findall(r"## Profile: (conn_\d+)", prompt_text)
            return json.dumps([
                {"connection_id": cid, "explanation": f"Explanation for {cid}.", "highlighted_attributes": []}
                for cid in ids
            ])
        mock_client.call_llm.side_effect = make_response
        mock_create_client.return_value = mock_client

        explainer = WhyThisPersonExplainer()
        # Create 25 results (should be 3 batches: 10, 10, 5)
        results = [
            _make_item(connection_id=f"conn_{i:03d}", crawled_profile_id=f"cp_{i:03d}")
            for i in range(25)
        ]
        explanations = explainer.explain("test query", results)

        assert mock_client.call_llm.call_count == 3  # ceil(25/10) = 3
        assert len(explanations) == 25

    def test_profile_key_falls_back_to_crawled_profile_id(self):
        """When connection_id is empty, _format_profile uses crawled_profile_id."""
        item = _make_item(connection_id="", crawled_profile_id="cp_fallback")
        result = _format_profile(item)
        assert "## Profile: cp_fallback" in result

    @patch("linkedout.intelligence.explainer.why_this_person.WhyThisPersonExplainer._fetch_enrichment_data")
    def test_prepare_enrichment_delegates_to_fetch(self, mock_fetch):
        mock_fetch.return_value = {"cp_001": {"experiences": []}}
        explainer = WhyThisPersonExplainer()
        results = [_make_item()]
        session = MagicMock()

        enrichment = explainer.prepare_enrichment(results, session)

        mock_fetch.assert_called_once_with(session, ["cp_001"], ["conn_001"])
        assert enrichment == {"cp_001": {"experiences": []}}

    def test_prepare_enrichment_empty_profiles(self):
        """No crawled_profile_id → returns {}."""
        explainer = WhyThisPersonExplainer()
        results = [_make_item(crawled_profile_id="", connection_id="conn_001")]
        session = MagicMock()

        assert explainer.prepare_enrichment(results, session) == {}

    @patch("linkedout.intelligence.explainer.why_this_person.WhyThisPersonExplainer._create_llm_client")
    @patch("linkedout.intelligence.explainer.why_this_person.WhyThisPersonExplainer.prepare_enrichment")
    def test_explain_uses_prepare_enrichment(self, mock_prep, mock_create_client):
        """explain() with a session delegates to prepare_enrichment internally."""
        mock_prep.return_value = {"cp_001": {"experiences": []}}
        mock_client = MagicMock()
        mock_client.call_llm.return_value = json.dumps([
            {"connection_id": "conn_001", "explanation": "Match.", "highlighted_attributes": []},
        ])
        mock_create_client.return_value = mock_client

        explainer = WhyThisPersonExplainer()
        session = MagicMock()
        results = [_make_item()]
        explainer.explain("test", results, session=session)

        mock_prep.assert_called_once_with(results, session)
