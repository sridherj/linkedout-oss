# SPDX-License-Identifier: Apache-2.0
"""Integration tests for multi-turn conversation persistence.

Verifies the turn-based flow: each search turn creates a search_turn row,
session.turn_count and last_active_at are updated, and turn history is
passed to the agent on continuation.
"""
import json

import pytest
from sqlalchemy import text
from unittest.mock import patch, MagicMock

from linkedout.intelligence.contracts import (
    ConversationTurnResponse,
    SearchResultItem,
)

pytestmark = pytest.mark.integration


def _make_turn_response(
    message: str,
    result_count: int = 2,
    query_type: str = "sql",
    transcript: list[dict] | None = None,
) -> ConversationTurnResponse:
    """Build a mock ConversationTurnResponse."""
    results = [
        SearchResultItem(
            connection_id=f"conn_{i}",
            crawled_profile_id=f"cp_{i}",
            full_name=f"Person {i}",
        )
        for i in range(result_count)
    ]
    return ConversationTurnResponse(
        message=message,
        results=results,
        query_type=query_type,
        turn_transcript=transcript or [{"role": "user", "content": message}],
    )


def _parse_sse_events(response_text: str) -> list[dict]:
    """Parse SSE event stream into list of dicts."""
    events = []
    for line in response_text.split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def _get_event(events: list[dict], event_type: str) -> dict | None:
    """Get first event of given type."""
    for e in events:
        if e.get("type") == event_type:
            return e
    return None


class TestMultiTurnConversation:
    """Full 4-turn conversation against real DB verifying turn persistence."""

    def _do_search(
        self,
        test_client,
        tenant_id: str,
        bu_id: str,
        app_user_id: str,
        query: str,
        session_id: str | None,
        mock_response: ConversationTurnResponse,
    ) -> tuple[str, list[dict]]:
        """Execute a search turn, return (session_id, sse_events)."""
        with patch(
            "linkedout.intelligence.agents.search_agent.SearchAgent"
        ) as MockAgent:
            mock_agent = MagicMock()
            mock_agent.run_turn.return_value = mock_response
            MockAgent.return_value = mock_agent

            body = {"query": query, "limit": 10}
            if session_id:
                body["session_id"] = session_id

            response = test_client.post(
                f"/tenants/{tenant_id}/bus/{bu_id}/search",
                json=body,
                headers={"X-App-User-Id": app_user_id},
                params={"explain": "false"},
            )

            assert response.status_code == 200
            events = _parse_sse_events(response.text)
            session_event = _get_event(events, "session")
            assert session_event is not None
            return session_event["payload"]["session_id"], events

    def test_four_turn_conversation(
        self, test_client, intelligence_test_data, integration_db_session,
    ):
        """Run 4 turns and verify search_turn rows are persisted."""
        user = intelligence_test_data["user_a"]
        tenant = intelligence_test_data["tenant"]
        bu = intelligence_test_data["bu"]

        # Turn 1 — initial search (no session_id)
        resp1 = _make_turn_response("Found Palo Alto connections", result_count=3)
        sid, events1 = self._do_search(
            test_client, tenant.id, bu.id, user.id,
            "find people who can connect me to Palo Alto Networks",
            session_id=None,
            mock_response=resp1,
        )
        assert _get_event(events1, "done") is not None

        # Turn 2 — broaden (same session)
        resp2 = _make_turn_response("Broader results", result_count=5)
        sid2, _ = self._do_search(
            test_client, tenant.id, bu.id, user.id,
            "anyone who worked with me",
            session_id=sid,
            mock_response=resp2,
        )
        assert sid2 == sid  # same session

        # Turn 3 — refine
        resp3 = _make_turn_response("Filtered to cybersecurity", result_count=2)
        sid3, _ = self._do_search(
            test_client, tenant.id, bu.id, user.id,
            "who among them are in cybersecurity",
            session_id=sid,
            mock_response=resp3,
        )
        assert sid3 == sid

        # Turn 4 — verify persistence
        resp4 = _make_turn_response("Company breakdown", result_count=1)
        sid4, _ = self._do_search(
            test_client, tenant.id, bu.id, user.id,
            "what companies are they at",
            session_id=sid,
            mock_response=resp4,
        )
        assert sid4 == sid

        # Verify: 4 search_turn rows exist for this session
        # Use a fresh read to avoid stale cache
        integration_db_session.expire_all()
        row = integration_db_session.execute(
            text("SELECT COUNT(*) FROM search_turn WHERE session_id = :sid"),
            {"sid": sid},
        ).scalar()
        assert row == 4, f"Expected 4 turn rows, got {row}"

    def test_new_session_created_without_session_id(
        self, test_client, intelligence_test_data,
    ):
        """Omitting session_id creates a new session each time."""
        user = intelligence_test_data["user_a"]
        tenant = intelligence_test_data["tenant"]
        bu = intelligence_test_data["bu"]

        resp = _make_turn_response("Results")
        sid1, _ = self._do_search(
            test_client, tenant.id, bu.id, user.id,
            "query one", session_id=None, mock_response=resp,
        )
        sid2, _ = self._do_search(
            test_client, tenant.id, bu.id, user.id,
            "query two", session_id=None, mock_response=resp,
        )
        assert sid1 != sid2

    def test_continuation_passes_turn_history_to_agent(
        self, test_client, intelligence_test_data,
    ):
        """When resuming a session, the agent receives prior turn history."""
        user = intelligence_test_data["user_a"]
        tenant = intelligence_test_data["tenant"]
        bu = intelligence_test_data["bu"]

        # Turn 1
        resp1 = _make_turn_response("First results", transcript=[
            {"role": "user", "content": "initial query"},
            {"role": "assistant", "content": "Found results"},
        ])

        with patch(
            "linkedout.intelligence.agents.search_agent.SearchAgent"
        ) as MockAgent:
            mock_agent = MagicMock()
            mock_agent.run_turn.return_value = resp1
            MockAgent.return_value = mock_agent

            response = test_client.post(
                f"/tenants/{tenant.id}/bus/{bu.id}/search",
                json={"query": "initial query", "limit": 10},
                headers={"X-App-User-Id": user.id},
                params={"explain": "false"},
            )
            events = _parse_sse_events(response.text)
            session_event = _get_event(events, "session")
            assert session_event is not None
            sid = session_event["payload"]["session_id"]

        # Turn 2 — capture what turn_history is passed to agent
        resp2 = _make_turn_response("Follow up results")

        with patch(
            "linkedout.intelligence.agents.search_agent.SearchAgent"
        ) as MockAgent:
            mock_agent = MagicMock()
            mock_agent.run_turn.return_value = resp2
            MockAgent.return_value = mock_agent

            test_client.post(
                f"/tenants/{tenant.id}/bus/{bu.id}/search",
                json={"query": "follow up", "limit": 10, "session_id": sid},
                headers={"X-App-User-Id": user.id},
                params={"explain": "false"},
            )

            # Verify agent.run_turn was called with turn_history
            call_kwargs = mock_agent.run_turn.call_args
            assert call_kwargs is not None
            turn_history = call_kwargs.kwargs.get("turn_history") or call_kwargs[1].get("turn_history")
            if turn_history is None and len(call_kwargs.args) > 1:
                turn_history = call_kwargs.args[1]

            assert turn_history is not None, "Agent should receive turn history on continuation"
            assert len(turn_history) >= 1, "Should have at least 1 prior turn"
            assert turn_history[0]["user_query"] == "initial query"

    def test_session_turn_count_incremented(
        self, test_client, intelligence_test_data, integration_db_session,
    ):
        """Session.turn_count reflects the number of turns."""
        user = intelligence_test_data["user_a"]
        tenant = intelligence_test_data["tenant"]
        bu = intelligence_test_data["bu"]

        resp = _make_turn_response("Results")
        sid, _ = self._do_search(
            test_client, tenant.id, bu.id, user.id,
            "first query", session_id=None, mock_response=resp,
        )
        self._do_search(
            test_client, tenant.id, bu.id, user.id,
            "second query", session_id=sid, mock_response=resp,
        )

        integration_db_session.expire_all()
        turn_count = integration_db_session.execute(
            text("SELECT turn_count FROM search_session WHERE id = :sid"),
            {"sid": sid},
        ).scalar()
        assert turn_count == 2, f"Expected turn_count=2, got {turn_count}"

    def test_sse_conversation_state_has_no_exclusion_state(
        self, test_client, intelligence_test_data,
    ):
        """SSE conversation_state event must NOT contain exclusion_state."""
        user = intelligence_test_data["user_a"]
        tenant = intelligence_test_data["tenant"]
        bu = intelligence_test_data["bu"]

        resp = _make_turn_response("Results")
        _, events = self._do_search(
            test_client, tenant.id, bu.id, user.id,
            "test query", session_id=None, mock_response=resp,
        )

        conv_state = _get_event(events, "conversation_state")
        assert conv_state is not None
        assert "exclusion_state" not in conv_state.get("payload", {})
