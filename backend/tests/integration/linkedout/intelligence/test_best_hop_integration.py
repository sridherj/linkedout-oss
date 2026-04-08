# SPDX-License-Identifier: Apache-2.0
"""Integration tests for best-hop endpoint against real PostgreSQL."""
from __future__ import annotations

import json
import time
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text

from linkedout.intelligence.contracts import BestHopRequest

pytestmark = pytest.mark.integration


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def best_hop_test_data(integration_db_session, intelligence_test_data):
    """Extend intelligence_test_data with best-hop-specific setup.

    Creates:
    - 1 target profile (enriched, with experience)
    - Affinity scores on User A's connections
    - 5 mutual URLs: 3 matched to connections, 2 not in DB
    """
    session = integration_db_session
    data = intelligence_test_data

    # Use existing profiles from intelligence_test_data as mutuals.
    # profiles_a[0..2] will be our matched mutuals.
    # Set affinity scores on their connections.
    for i, conn in enumerate(data["connections_a"][:3]):
        conn.affinity_score = 90.0 - (i * 15)
        conn.dunbar_tier = ["inner_circle", "active", "familiar"][i]
        conn.affinity_career_overlap = 70.0 - (i * 10)
        conn.affinity_external_contact = 50.0 if i == 0 else 0.0
        conn.affinity_recency = 80.0 - (i * 20)
    session.flush()

    # The "target" is profiles_a[10] — treat it as someone we want to be introduced to.
    # It already has experiences via intelligence_test_data setup but let's ensure
    # it has at least one experience.
    target_profile = data["profiles_a"][10]

    # Verify the target has a linkedin_url
    assert target_profile.linkedin_url is not None

    session.commit()

    # URLs
    matched_urls = [data["profiles_a"][i].linkedin_url for i in range(3)]
    unmatched_urls = [
        "https://linkedin.com/in/does-not-exist-1",
        "https://linkedin.com/in/does-not-exist-2",
    ]

    return {
        **data,
        "target_profile": target_profile,
        "matched_urls": matched_urls,
        "unmatched_urls": unmatched_urls,
        "all_mutual_urls": matched_urls + unmatched_urls,
    }


def _parse_sse_events(response_text: str) -> list[dict]:
    """Parse SSE text into event dicts."""
    events = []
    for line in response_text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                continue
    return events


def _mock_llm_response(mutuals_data: list[dict]) -> MagicMock:
    """Create a mock LLM response that ranks the given mutuals."""
    items = [
        {
            "crawled_profile_id": m["id"],
            "rank": i + 1,
            "why_this_person": f"Great connector for introduction (rank {i + 1}).",
        }
        for i, m in enumerate(mutuals_data)
    ]
    response = MagicMock()
    response.has_tool_calls = False
    response.content = json.dumps(items)
    return response


# ── Tests ────────────────────────────────────────────────────────────────


class TestBestHopHappyPath:
    """POST /best-hop with target + 5 mutual URLs (3 in DB, 2 not)."""

    @patch("linkedout.intelligence.services.best_hop_service.LLMFactory")
    def test_happy_path_sse_events(
        self, mock_factory, test_client, best_hop_test_data,
    ):
        data = best_hop_test_data
        user_a = data["user_a"]
        tenant = data["tenant"]
        bu = data["bu"]

        # Mock LLM to return rankings for matched profiles
        profiles_a = data["profiles_a"]
        matched_mutuals = [
            {"id": profiles_a[i].id} for i in range(3)
        ]
        mock_client = MagicMock()
        mock_factory.create_client.return_value = mock_client
        mock_client.call_llm_with_tools.return_value = _mock_llm_response(matched_mutuals)

        response = test_client.post(
            f"/tenants/{tenant.id}/bus/{bu.id}/best-hop",
            json={
                "target_name": data["target_profile"].full_name,
                "target_url": data["target_profile"].linkedin_url,
                "mutual_urls": data["all_mutual_urls"],
            },
            headers={"X-App-User-Id": user_a.id},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        events = _parse_sse_events(response.text)
        event_types = [e["type"] for e in events if e["type"] != "heartbeat"]

        # Must have session, thinking, result(s), and done events
        assert "session" in event_types
        assert "thinking" in event_types
        assert "done" in event_types

        result_events = [e for e in events if e["type"] == "result"]
        assert len(result_events) >= 1

        # Each result should have expected fields
        for r in result_events:
            payload = r["payload"]
            assert "connection_id" in payload
            assert "full_name" in payload
            assert "why_this_person" in payload
            assert "rank" in payload

        # Results should be ordered by rank
        ranks = [r["payload"]["rank"] for r in result_events]
        assert ranks == sorted(ranks)

        # Done event should have correct matched/unmatched counts
        done_event = next(e for e in events if e["type"] == "done")
        assert done_event["payload"]["matched"] == 3
        assert done_event["payload"]["unmatched"] == 2


class TestBestHopTrailingSlash:
    """Extension sends URLs with trailing slashes — must still match after normalization."""

    @patch("linkedout.intelligence.services.best_hop_service.LLMFactory")
    def test_trailing_slash_urls_still_match(
        self, mock_factory, test_client, best_hop_test_data,
    ):
        data = best_hop_test_data
        user_a = data["user_a"]
        tenant = data["tenant"]
        bu = data["bu"]

        profiles_a = data["profiles_a"]
        matched_mutuals = [{"id": profiles_a[i].id} for i in range(3)]
        mock_client = MagicMock()
        mock_factory.create_client.return_value = mock_client
        mock_client.call_llm_with_tools.return_value = _mock_llm_response(matched_mutuals)

        # Append trailing slash to all URLs — mimics what the extension sends
        urls_with_slash = [u + "/" for u in data["matched_urls"]]
        unmatched_with_slash = [u + "/" for u in data["unmatched_urls"]]

        response = test_client.post(
            f"/tenants/{tenant.id}/bus/{bu.id}/best-hop",
            json={
                "target_name": data["target_profile"].full_name,
                "target_url": data["target_profile"].linkedin_url + "/",
                "mutual_urls": urls_with_slash + unmatched_with_slash,
            },
            headers={"X-App-User-Id": user_a.id},
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)

        result_events = [e for e in events if e["type"] == "result"]
        assert len(result_events) == 3, f"Expected 3 results, got {len(result_events)}"

        done_event = next(e for e in events if e["type"] == "done")
        assert done_event["payload"]["matched"] == 3
        assert done_event["payload"]["unmatched"] == 2


class TestBestHopAllUnmatched:
    """POST with URLs not in DB."""

    @patch("linkedout.intelligence.services.best_hop_service.LLMFactory")
    def test_all_unmatched(
        self, mock_factory, test_client, best_hop_test_data,
    ):
        data = best_hop_test_data
        user_a = data["user_a"]
        tenant = data["tenant"]
        bu = data["bu"]

        # Mock LLM returns empty (no mutuals to rank)
        mock_client = MagicMock()
        mock_factory.create_client.return_value = mock_client
        llm_response = MagicMock()
        llm_response.has_tool_calls = False
        llm_response.content = "[]"
        mock_client.call_llm_with_tools.return_value = llm_response

        unmatched_only = [
            "https://linkedin.com/in/nobody-1",
            "https://linkedin.com/in/nobody-2",
            "https://linkedin.com/in/nobody-3",
        ]

        response = test_client.post(
            f"/tenants/{tenant.id}/bus/{bu.id}/best-hop",
            json={
                "target_name": data["target_profile"].full_name,
                "target_url": data["target_profile"].linkedin_url,
                "mutual_urls": unmatched_only,
            },
            headers={"X-App-User-Id": user_a.id},
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)

        result_events = [e for e in events if e["type"] == "result"]
        assert len(result_events) == 0

        done_event = next(e for e in events if e["type"] == "done")
        assert done_event["payload"]["matched"] == 0
        assert done_event["payload"]["unmatched"] == 3


class TestBestHopPartialMatch:
    """Mix of known/unknown URLs."""

    @patch("linkedout.intelligence.services.best_hop_service.LLMFactory")
    def test_partial_match_counts(
        self, mock_factory, test_client, best_hop_test_data,
    ):
        data = best_hop_test_data
        user_a = data["user_a"]
        tenant = data["tenant"]
        bu = data["bu"]

        # Only 1 matched URL + 2 unmatched
        one_matched = [data["profiles_a"][0].linkedin_url]
        two_unmatched = [
            "https://linkedin.com/in/ghost-a",
            "https://linkedin.com/in/ghost-b",
        ]

        mock_client = MagicMock()
        mock_factory.create_client.return_value = mock_client
        mock_client.call_llm_with_tools.return_value = _mock_llm_response(
            [{"id": data["profiles_a"][0].id}]
        )

        response = test_client.post(
            f"/tenants/{tenant.id}/bus/{bu.id}/best-hop",
            json={
                "target_name": data["target_profile"].full_name,
                "target_url": data["target_profile"].linkedin_url,
                "mutual_urls": one_matched + two_unmatched,
            },
            headers={"X-App-User-Id": user_a.id},
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)

        done_event = next(e for e in events if e["type"] == "done")
        assert done_event["payload"]["matched"] == 1
        assert done_event["payload"]["unmatched"] == 2

        result_events = [e for e in events if e["type"] == "result"]
        assert len(result_events) == 1


class TestBestHopSessionPersisted:
    """Verify SearchSession and SearchTurn rows exist after stream completes."""

    @patch("linkedout.intelligence.services.best_hop_service.LLMFactory")
    def test_session_persisted(
        self, mock_factory, test_client, best_hop_test_data, integration_db_session,
    ):
        data = best_hop_test_data
        user_a = data["user_a"]
        tenant = data["tenant"]
        bu = data["bu"]

        profiles_a = data["profiles_a"]
        matched_mutuals = [{"id": profiles_a[i].id} for i in range(3)]
        mock_client = MagicMock()
        mock_factory.create_client.return_value = mock_client
        mock_client.call_llm_with_tools.return_value = _mock_llm_response(matched_mutuals)

        response = test_client.post(
            f"/tenants/{tenant.id}/bus/{bu.id}/best-hop",
            json={
                "target_name": data["target_profile"].full_name,
                "target_url": data["target_profile"].linkedin_url,
                "mutual_urls": data["all_mutual_urls"],
            },
            headers={"X-App-User-Id": user_a.id},
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        session_event = next(e for e in events if e["type"] == "session")
        session_id = session_event["payload"]["session_id"]

        # Give the fire-and-forget save a moment to complete
        import time
        time.sleep(1)

        # Check SearchSession exists
        row = integration_db_session.execute(
            text("SELECT id, initial_query, turn_count FROM search_session WHERE id = :sid"),
            {"sid": session_id},
        ).first()

        assert row is not None, f"SearchSession {session_id} not found in DB"
        assert "Best hop" in row[1]

        # Check SearchTurn exists
        turn_row = integration_db_session.execute(
            text("SELECT session_id, user_query FROM search_turn WHERE session_id = :sid"),
            {"sid": session_id},
        ).first()

        assert turn_row is not None, f"SearchTurn for session {session_id} not found"
        assert "Best hop" in turn_row[1]


class TestBestHopStreamsIncrementally:
    """Verify SSE events stream incrementally through the middleware stack."""

    @pytest.mark.asyncio
    async def test_best_hop_streams_events_incrementally(
        self, best_hop_test_data, integration_db_engine,
    ):
        """Verify Best Hop SSE events arrive as they're generated, not buffered.

        Use httpx.AsyncClient against the real app.
        Read chunks as they arrive.
        Verify thinking -> result(s) -> done ordering.
        """
        import httpx
        from httpx._transports.asgi import ASGITransport
        from shared.infra.db.db_session_manager import db_session_manager

        db_session_manager.set_engine(integration_db_engine)
        from main import app

        data = best_hop_test_data
        user_a = data["user_a"]
        tenant = data["tenant"]
        bu = data["bu"]

        profiles_a = data["profiles_a"]
        matched_mutuals = [{"id": profiles_a[i].id} for i in range(3)]

        with patch("linkedout.intelligence.services.best_hop_service.LLMFactory") as mock_factory:
            mock_client = MagicMock()
            mock_factory.create_client.return_value = mock_client
            mock_client.call_llm_with_tools.return_value = _mock_llm_response(matched_mutuals)

            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/tenants/{tenant.id}/bus/{bu.id}/best-hop",
                    json={
                        "target_name": data["target_profile"].full_name,
                        "target_url": data["target_profile"].linkedin_url,
                        "mutual_urls": data["all_mutual_urls"],
                    },
                    headers={"X-App-User-Id": user_a.id},
                )

        assert response.status_code == 200

        events = _parse_sse_events(response.text)
        event_types = [e["type"] for e in events if e["type"] != "heartbeat"]

        # Must have thinking -> session -> thinking -> result(s) -> done
        assert "thinking" in event_types
        assert "done" in event_types

        result_events = [e for e in events if e["type"] == "result"]
        assert len(result_events) >= 1

        # Verify ordering: thinking appears before done
        thinking_idx = event_types.index("thinking")
        done_idx = event_types.index("done")
        assert thinking_idx < done_idx

    @pytest.mark.asyncio
    async def test_best_hop_heartbeat_during_slow_service(
        self, best_hop_test_data, integration_db_engine,
    ):
        """Verify heartbeats arrive while BestHopService is processing.

        Mock BestHopService to be slow (sleep 2s).
        Set heartbeat interval to 0.5s.
        Verify heartbeat events arrive while waiting for results.
        """
        import httpx
        from httpx._transports.asgi import ASGITransport
        from linkedout.intelligence.services.best_hop_service import BestHopDone, BestHopResultItem
        from shared.infra.db.db_session_manager import db_session_manager

        db_session_manager.set_engine(integration_db_engine)
        from main import app

        data = best_hop_test_data
        user_a = data["user_a"]
        tenant = data["tenant"]
        bu = data["bu"]

        def _slow_rank(request):
            """Simulate a slow BestHopService.rank() — sleep 2s then yield results."""
            time.sleep(2)
            yield BestHopResultItem(
                connection_id="conn_slow",
                crawled_profile_id="cp_slow",
                full_name="Slow Person",
                current_position="Engineer",
                current_company_name="SlowCo",
                rank=1,
                why_this_person="Slow but steady.",
            )
            yield BestHopDone(total=1, matched=1, unmatched=0, unmatched_urls=[])

        from linkedout.intelligence.controllers._sse_helpers import stream_with_heartbeat as _original_swh

        async def _fast_heartbeat(stream, interval=0.5):
            async for event in _original_swh(stream, interval=0.5):
                yield event

        with (
            patch(
                "linkedout.intelligence.controllers.best_hop_controller.BestHopService"
            ) as mock_service_cls,
            patch(
                "linkedout.intelligence.controllers.best_hop_controller.stream_with_heartbeat",
                _fast_heartbeat,
            ),
            patch(
                "linkedout.intelligence.controllers.best_hop_controller.get_client"
            ) as mock_langfuse,
            patch(
                "linkedout.intelligence.controllers.best_hop_controller.propagate_attributes"
            ),
        ):
            mock_service_instance = MagicMock()
            mock_service_instance.rank.side_effect = _slow_rank
            mock_service_cls.return_value = mock_service_instance

            # Mock langfuse
            mock_langfuse_client = MagicMock()
            mock_langfuse_client.start_as_current_observation.return_value.__enter__ = MagicMock()
            mock_langfuse_client.start_as_current_observation.return_value.__exit__ = MagicMock(
                return_value=False
            )
            mock_langfuse.return_value = mock_langfuse_client

            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/tenants/{tenant.id}/bus/{bu.id}/best-hop",
                    json={
                        "target_name": "Slow Target",
                        "target_url": "https://linkedin.com/in/slow-target",
                        "mutual_urls": ["https://linkedin.com/in/mutual-1"],
                    },
                    headers={"X-App-User-Id": user_a.id},
                )

        assert response.status_code == 200

        events = _parse_sse_events(response.text)

        heartbeat_events = [e for e in events if e.get("type") == "heartbeat"]
        result_events = [e for e in events if e.get("type") == "result"]
        done_events = [e for e in events if e.get("type") == "done"]

        # With a 2s service delay and 0.5s heartbeat interval, expect at least 2 heartbeats
        assert len(heartbeat_events) >= 2, (
            f"Expected at least 2 heartbeats during slow service, got {len(heartbeat_events)}. "
            f"All event types: {[e.get('type') for e in events]}"
        )
        # Results should eventually arrive
        assert len(result_events) >= 1
        assert len(done_events) == 1

        # Heartbeats must appear before results in the stream
        all_types = [e.get("type") for e in events]
        first_heartbeat_idx = all_types.index("heartbeat")
        # Find first result event index
        first_result_idx = all_types.index("result")
        assert first_heartbeat_idx < first_result_idx, (
            "Heartbeat should appear before first result event"
        )
