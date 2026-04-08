# SPDX-License-Identifier: Apache-2.0
"""Test that the search controller streams explanations in multiple batches."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from linkedout.intelligence.contracts import (
    ConversationTurnResponse,
    ProfileExplanation,
    ResultMetadata,
    SearchResultItem,
)
from linkedout.intelligence.controllers._sse_helpers import merge_results_with_explanations


def _make_item(connection_id: str, crawled_profile_id: str) -> SearchResultItem:
    return SearchResultItem(
        connection_id=connection_id,
        crawled_profile_id=crawled_profile_id,
        full_name=f"Person {connection_id}",
        headline="Engineer",
        current_position="Engineer",
        current_company_name="Corp",
    )


def _make_turn_response(results: list[SearchResultItem]) -> ConversationTurnResponse:
    return ConversationTurnResponse(
        results=results,
        message="Found results",
        query_type="search",
        result_summary_chips=[],
        suggested_actions=[],
        result_metadata=ResultMetadata(total_found=len(results), query_interpreted="test"),
        facets=[],
    )


def _parse_sse_events(raw_lines: list[str]) -> list[dict]:
    """Parse SSE lines into event dicts."""
    events = []
    for line in raw_lines:
        line = line.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


@pytest.mark.asyncio
@patch("linkedout.intelligence.controllers.search_controller.create_or_resume_session")
@patch("linkedout.intelligence.controllers.search_controller.db_session_manager")
@patch("linkedout.intelligence.controllers.search_controller.get_client")
@patch("linkedout.intelligence.agents.search_agent.SearchAgent")
@patch("linkedout.intelligence.explainer.why_this_person.WhyThisPersonExplainer.prepare_enrichment")
@patch("linkedout.intelligence.explainer.why_this_person.WhyThisPersonExplainer.explain_batch")
async def test_streams_multiple_explanation_events_for_large_result_sets(
    mock_explain_batch,
    mock_prepare,
    mock_agent_cls,
    mock_langfuse,
    mock_db,
    mock_create_session,
):
    """With 25 results (3 batches of 10,10,5), the SSE stream should contain 3 separate explanation events."""
    from linkedout.intelligence.controllers.search_controller import _stream_search
    from linkedout.intelligence.contracts import SearchRequest

    # 25 results → 3 batches
    results = [_make_item(f"conn_{i:03d}", f"cp_{i:03d}") for i in range(25)]
    turn_response = _make_turn_response(results)

    # Mock session creation
    mock_create_session.return_value = ("sess_123", [])

    # Mock agent
    mock_agent_instance = MagicMock()
    mock_agent_instance.run_turn.return_value = turn_response
    mock_agent_cls.return_value = mock_agent_instance

    # Mock langfuse context manager
    mock_langfuse_client = MagicMock()
    mock_langfuse_client.start_as_current_observation.return_value.__enter__ = MagicMock()
    mock_langfuse_client.start_as_current_observation.return_value.__exit__ = MagicMock(return_value=False)
    mock_langfuse.return_value = mock_langfuse_client

    # Mock DB session manager
    mock_session = MagicMock()
    mock_db.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)

    # Mock enrichment
    mock_prepare.return_value = {f"cp_{i:03d}": {"experiences": []} for i in range(25)}

    # Mock explain_batch — return explanations keyed by connection_id
    def fake_explain_batch(query, batch, enrichment_map):
        return {
            item.connection_id: ProfileExplanation(
                explanation=f"Match for {item.connection_id}",
                highlighted_attributes=[],
            )
            for item in batch
        }
    mock_explain_batch.side_effect = fake_explain_batch

    request = SearchRequest(query="test query")

    # Collect all SSE lines
    sse_lines = []
    async for line in _stream_search("t1", "bu1", "user1", request, explain=True):
        sse_lines.append(line)

    events = _parse_sse_events(sse_lines)
    explanation_events = [e for e in events if e.get("type") == "explanations"]

    # Should have 3 separate explanation events, not 1
    assert len(explanation_events) == 3
    # First batch should have 10 explanations
    assert len(explanation_events[0]["payload"]) == 10
    # Second batch should have 10
    assert len(explanation_events[1]["payload"]) == 10
    # Third batch should have 5
    assert len(explanation_events[2]["payload"]) == 5
    # Total explanations across all events
    total = sum(len(e["payload"]) for e in explanation_events)
    assert total == 25


# ---------------------------------------------------------------------------
# _merge_results_with_explanations tests
# ---------------------------------------------------------------------------

class TestMergeResultsWithExplanations:
    def test_merges_matching_explanations(self):
        items = [_make_item("conn_001", "cp_001"), _make_item("conn_002", "cp_002")]
        explanations = {
            "conn_001": {
                "explanation": "Great match",
                "highlighted_attributes": ["Python", "AI"],
                "match_strength": "strong",
            },
            "conn_002": {
                "explanation": "Good fit",
                "highlighted_attributes": ["Go"],
                "match_strength": "moderate",
            },
        }
        merged = merge_results_with_explanations(items, explanations)
        assert merged[0]["why_this_person"] == "Great match"
        assert merged[0]["highlighted_attributes"] == ["Python", "AI"]
        assert merged[0]["match_strength"] == "strong"
        assert merged[1]["why_this_person"] == "Good fit"

    def test_no_matching_explanations_leaves_plain_dump(self):
        items = [_make_item("conn_001", "cp_001")]
        explanations = {"conn_999": {"explanation": "Unrelated"}}
        merged = merge_results_with_explanations(items, explanations)
        assert "why_this_person" not in merged[0]
        assert "highlighted_attributes" not in merged[0]
        assert "match_strength" not in merged[0]

    def test_none_explanations_returns_plain_dump(self):
        items = [_make_item("conn_001", "cp_001")]
        merged = merge_results_with_explanations(items, None)
        assert merged[0]["connection_id"] == "conn_001"
        assert "why_this_person" not in merged[0]

    def test_empty_explanations_returns_plain_dump(self):
        items = [_make_item("conn_001", "cp_001")]
        merged = merge_results_with_explanations(items, {})
        assert "why_this_person" not in merged[0]

    def test_fallback_to_crawled_profile_id(self):
        """When connection_id has no match, falls back to crawled_profile_id."""
        item = _make_item("conn_001", "cp_001")
        explanations = {
            "cp_001": {
                "explanation": "Matched via profile ID",
                "highlighted_attributes": [],
                "match_strength": "weak",
            },
        }
        merged = merge_results_with_explanations([item], explanations)
        assert merged[0]["why_this_person"] == "Matched via profile ID"


# ---------------------------------------------------------------------------
# Verify explanations are passed to _save_session_state
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("linkedout.intelligence.controllers.search_controller.save_session_state")
@patch("linkedout.intelligence.controllers.search_controller.create_or_resume_session")
@patch("linkedout.intelligence.controllers.search_controller.db_session_manager")
@patch("linkedout.intelligence.controllers.search_controller.get_client")
@patch("linkedout.intelligence.agents.search_agent.SearchAgent")
@patch("linkedout.intelligence.explainer.why_this_person.WhyThisPersonExplainer.prepare_enrichment")
@patch("linkedout.intelligence.explainer.why_this_person.WhyThisPersonExplainer.explain_batch")
async def test_save_session_state_receives_accumulated_explanations(
    mock_explain_batch,
    mock_prepare,
    mock_agent_cls,
    mock_langfuse,
    mock_db,
    mock_create_session,
    mock_save,
):
    """_save_session_state should be called with all_explanations containing 25 entries."""
    from linkedout.intelligence.controllers.search_controller import _stream_search
    from linkedout.intelligence.contracts import SearchRequest

    results = [_make_item(f"conn_{i:03d}", f"cp_{i:03d}") for i in range(25)]
    turn_response = _make_turn_response(results)

    mock_create_session.return_value = ("sess_123", [])

    mock_agent_instance = MagicMock()
    mock_agent_instance.run_turn.return_value = turn_response
    mock_agent_cls.return_value = mock_agent_instance

    mock_langfuse_client = MagicMock()
    mock_langfuse_client.start_as_current_observation.return_value.__enter__ = MagicMock()
    mock_langfuse_client.start_as_current_observation.return_value.__exit__ = MagicMock(return_value=False)
    mock_langfuse.return_value = mock_langfuse_client

    mock_session = MagicMock()
    mock_db.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)

    mock_prepare.return_value = {f"cp_{i:03d}": {"experiences": []} for i in range(25)}

    def fake_explain_batch(query, batch, enrichment_map):
        return {
            item.connection_id: ProfileExplanation(
                explanation=f"Match for {item.connection_id}",
                highlighted_attributes=[],
            )
            for item in batch
        }
    mock_explain_batch.side_effect = fake_explain_batch

    request = SearchRequest(query="test query")

    # Drain the generator
    async for _ in _stream_search("t1", "bu1", "user1", request, explain=True):
        pass

    # Verify _save_session_state was called with explanations
    mock_save.assert_called_once()
    args = mock_save.call_args
    assert args[0][0] == "sess_123"  # session_id
    assert args[0][1] == "test query"  # user_query
    assert args[0][2] is turn_response  # turn_response
    all_explanations = args[0][3]  # explanations
    assert len(all_explanations) == 25
    assert "conn_000" in all_explanations
    assert all_explanations["conn_000"]["explanation"] == "Match for conn_000"


# ---------------------------------------------------------------------------
# Heartbeat regression test — BaseHTTPMiddleware buffering bug
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_reaches_client_during_slow_llm():
    """Regression test for BaseHTTPMiddleware buffering bug.

    Mock SearchAgent to take 2+ seconds to respond.
    Set heartbeat interval to 0.5s.
    Verify heartbeat events appear in the SSE output BEFORE the final results.

    This is the exact scenario that was broken: long LLM calls caused
    heartbeats to be buffered by BaseHTTPMiddleware, never reaching the client.
    """
    import httpx
    from httpx._transports.asgi import ASGITransport

    from linkedout.intelligence.contracts import (
        ResultMetadata,
        SearchRequest,
    )

    # Build results that the slow agent will eventually return
    results = [_make_item("conn_slow_0", "cp_slow_0")]
    turn_response = _make_turn_response(results)

    from linkedout.intelligence.controllers._sse_helpers import stream_with_heartbeat as _original_swh

    async def _fast_heartbeat(stream, interval=0.5):
        async for event in _original_swh(stream, interval=0.5):
            yield event

    with (
        patch(
            "linkedout.intelligence.controllers.search_controller.create_or_resume_session",
            return_value=("sess_heartbeat", []),
        ),
        patch("linkedout.intelligence.controllers.search_controller.db_session_manager") as mock_db,
        patch("linkedout.intelligence.controllers.search_controller.get_client") as mock_langfuse,
        patch("linkedout.intelligence.agents.search_agent.SearchAgent") as mock_agent_cls,
        patch(
            "linkedout.intelligence.controllers.search_controller.stream_with_heartbeat",
            _fast_heartbeat,
        ),
        patch(
            "linkedout.intelligence.controllers.search_controller.save_session_state",
        ),
    ):
        # Mock langfuse
        mock_langfuse_client = MagicMock()
        mock_langfuse_client.start_as_current_observation.return_value.__enter__ = MagicMock()
        mock_langfuse_client.start_as_current_observation.return_value.__exit__ = MagicMock(
            return_value=False
        )
        mock_langfuse.return_value = mock_langfuse_client

        # Mock DB session
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        # Mock agent — make run_turn synchronous but wrap the call in asyncio.to_thread
        # so we need the mock to sleep synchronously
        import time

        def slow_run_turn(*args, **kwargs):
            time.sleep(2)
            return turn_response

        mock_agent_instance = MagicMock()
        mock_agent_instance.run_turn.side_effect = slow_run_turn
        mock_agent_cls.return_value = mock_agent_instance

        from main import app

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/tenants/t1/bus/bu1/search?explain=false",
                json={"query": "test heartbeat query"},
                headers={"X-App-User-Id": "user1"},
            )

        assert response.status_code == 200

        events = _parse_sse_events(response.text.split("\n"))

        heartbeat_events = [e for e in events if e.get("type") == "heartbeat"]
        result_events = [e for e in events if e.get("type") == "result"]
        done_events = [e for e in events if e.get("type") == "done"]

        # With a 2s agent delay and 0.5s heartbeat interval, expect at least 2 heartbeats
        assert len(heartbeat_events) >= 2, (
            f"Expected at least 2 heartbeats before results, got {len(heartbeat_events)}. "
            f"All event types: {[e.get('type') for e in events]}"
        )
        # Results should eventually arrive
        assert len(result_events) >= 1
        assert len(done_events) == 1

        # Heartbeats must appear before results in the stream
        all_types = [e.get("type") for e in events]
        first_heartbeat_idx = all_types.index("heartbeat")
        first_result_idx = all_types.index("result")
        assert first_heartbeat_idx < first_result_idx, (
            "Heartbeat should appear before first result event"
        )
