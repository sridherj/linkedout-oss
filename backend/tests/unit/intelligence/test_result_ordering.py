# SPDX-License-Identifier: Apache-2.0
"""Tests for search result merge dedup, declared ordering, candidate count tracking, and streaming."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from linkedout.intelligence.agents.search_agent import SearchAgent
from linkedout.intelligence.contracts import SearchEvent, SearchResultItem


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_item(
    cpid: str,
    full_name: str = "",
    headline: str | None = None,
    affinity_score: float | None = None,
    similarity_score: float | None = None,
    match_context: dict | None = None,
    **kwargs,
) -> SearchResultItem:
    return SearchResultItem(
        connection_id=kwargs.get("connection_id", ""),
        crawled_profile_id=cpid,
        full_name=full_name,
        headline=headline,
        affinity_score=affinity_score,
        similarity_score=similarity_score,
        match_context=match_context,
    )


def _make_agent() -> SearchAgent:
    """Create a SearchAgent with mocked DB session and dependencies."""
    mock_session = MagicMock()
    mock_session.get.return_value = None  # no AppUserEntity
    with patch("linkedout.intelligence.agents.search_agent.build_schema_context", return_value="schema"):
        agent = SearchAgent(
            session=mock_session,
            app_user_id="usr_test",
        )
    return agent


def _build_messages_with_tool_results(
    tool_results: list[tuple[str, str, str]],
) -> list[dict]:
    """Build a minimal message list with tool call/result pairs.

    Each tuple: (tool_name, tool_call_id, result_json_str)
    """
    messages: list[dict] = []
    for tool_name, tc_id, result_str in tool_results:
        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": tc_id, "name": tool_name, "args": {}}],
        })
        messages.append({
            "role": "tool",
            "content": result_str,
            "tool_call_id": tc_id,
        })
    return messages


# ── Merge dedup tests ─────────────────────────────────────────────────────────

class TestMergeDedup:
    def test_combines_match_context(self):
        """Same profile from vector (has similarity_score) and SQL (has match_context) — both preserved."""
        agent = _make_agent()

        vector_data = [
            {"connection_id": "conn_1", "id": "cp_1", "full_name": "Alice", "similarity": 0.92},
        ]
        sql_data = {
            "columns": ["crawled_profile_id", "full_name", "years_experience"],
            "rows": [["cp_1", "Alice", 12]],
        }

        messages = _build_messages_with_tool_results([
            ("search_profiles", "tc_1", json.dumps(vector_data)),
            ("execute_sql", "tc_2", json.dumps(sql_data)),
        ])

        results = agent._collect_results(messages)
        assert len(results) == 1
        item = results[0]
        assert item.crawled_profile_id == "cp_1"
        assert item.similarity_score == 0.92
        assert item.match_context is not None
        assert item.match_context["years_experience"] == 12

    def test_fills_null_fields(self):
        """Later occurrence fills null fields on the first occurrence."""
        agent = _make_agent()

        vector_data = [
            {"connection_id": "conn_1", "id": "cp_1", "full_name": "Alice"},
        ]
        sql_data = {
            "columns": ["crawled_profile_id", "full_name", "headline"],
            "rows": [["cp_1", "Alice", "ML Engineer"]],
        }

        messages = _build_messages_with_tool_results([
            ("search_profiles", "tc_1", json.dumps(vector_data)),
            ("execute_sql", "tc_2", json.dumps(sql_data)),
        ])

        results = agent._collect_results(messages)
        assert len(results) == 1
        assert results[0].headline == "ML Engineer"

    def test_preserves_first_non_null(self):
        """First non-null value wins — later occurrence doesn't overwrite."""
        agent = _make_agent()

        sql_data_1 = {
            "columns": ["crawled_profile_id", "full_name", "affinity_score"],
            "rows": [["cp_1", "Alice", 45.0]],
        }
        sql_data_2 = {
            "columns": ["crawled_profile_id", "full_name", "affinity_score"],
            "rows": [["cp_1", "Alice", 30.0]],
        }

        messages = _build_messages_with_tool_results([
            ("execute_sql", "tc_1", json.dumps(sql_data_1)),
            ("execute_sql", "tc_2", json.dumps(sql_data_2)),
        ])

        results = agent._collect_results(messages)
        assert len(results) == 1
        assert results[0].affinity_score == 45.0


# ── Declared ordering tests ──────────────────────────────────────────────────

class TestDeclaredOrdering:
    def test_reorders_results(self):
        """Results reordered to match declared order."""
        agent = _make_agent()
        agent._declared_order = ["cp_C", "cp_A", "cp_B"]

        sql_data = {
            "columns": ["crawled_profile_id", "full_name"],
            "rows": [["cp_A", "Alice"], ["cp_B", "Bob"], ["cp_C", "Carol"]],
        }
        messages = _build_messages_with_tool_results([
            ("execute_sql", "tc_1", json.dumps(sql_data)),
        ])

        results = agent._collect_results(messages)
        assert [r.crawled_profile_id for r in results] == ["cp_C", "cp_A", "cp_B"]

    def test_unmentioned_append_at_end(self):
        """Profiles not in declared order appear after ordered ones."""
        agent = _make_agent()
        agent._declared_order = ["cp_C", "cp_A"]

        sql_data = {
            "columns": ["crawled_profile_id", "full_name"],
            "rows": [["cp_A", "Alice"], ["cp_B", "Bob"], ["cp_C", "Carol"], ["cp_D", "Dave"]],
        }
        messages = _build_messages_with_tool_results([
            ("execute_sql", "tc_1", json.dumps(sql_data)),
        ])

        results = agent._collect_results(messages)
        ids = [r.crawled_profile_id for r in results]
        assert ids[:2] == ["cp_C", "cp_A"]
        # B and D are unordered, but both present
        assert set(ids[2:]) == {"cp_B", "cp_D"}

    def test_unknown_ids_ignored(self):
        """IDs not in collected results are silently skipped."""
        agent = _make_agent()
        agent._declared_order = ["cp_X", "cp_A", "cp_Y", "cp_B"]

        sql_data = {
            "columns": ["crawled_profile_id", "full_name"],
            "rows": [["cp_A", "Alice"], ["cp_B", "Bob"]],
        }
        messages = _build_messages_with_tool_results([
            ("execute_sql", "tc_1", json.dumps(sql_data)),
        ])

        results = agent._collect_results(messages)
        assert [r.crawled_profile_id for r in results] == ["cp_A", "cp_B"]

    def test_no_declared_order_preserves_collection_order(self):
        """Without set_result_order, results stay in tool-call order (fallback)."""
        agent = _make_agent()
        # _declared_order is empty by default

        sql_data = {
            "columns": ["crawled_profile_id", "full_name"],
            "rows": [["cp_A", "Alice"], ["cp_B", "Bob"], ["cp_C", "Carol"]],
        }
        messages = _build_messages_with_tool_results([
            ("execute_sql", "tc_1", json.dumps(sql_data)),
        ])

        results = agent._collect_results(messages)
        assert [r.crawled_profile_id for r in results] == ["cp_A", "cp_B", "cp_C"]


# ── set_result_order handler tests ────────────────────────────────────────────

class TestSetResultOrderHandler:
    def test_handler_stores_order_and_returns_ok(self):
        """set_result_order handler stores declared order and returns confirmation."""
        agent = _make_agent()
        result_str = agent._execute_tool("set_result_order", {"profile_ids": ["cp_A", "cp_B", "cp_C"]})
        result = json.loads(result_str)

        assert result["status"] == "ok"
        assert result["ordered_count"] == 3
        assert agent._declared_order == ["cp_A", "cp_B", "cp_C"]

    def test_handler_sets_candidate_count_zero(self):
        """set_result_order is not a result-producing tool — candidate count stays 0."""
        agent = _make_agent()
        agent._last_candidate_count = 42  # set from prior tool
        agent._execute_tool("set_result_order", {"profile_ids": ["cp_A"]})
        assert agent._last_candidate_count == 0


# ── _last_candidate_count tests ───────────────────────────────────────────────

class TestCandidateCount:
    def test_search_profiles_sets_count(self):
        """search_profiles sets _last_candidate_count to number of results."""
        agent = _make_agent()
        mock_rows = [{"id": "cp_1"}, {"id": "cp_2"}, {"id": "cp_3"}]
        with patch("linkedout.intelligence.agents.search_agent.search_profiles", return_value=mock_rows):
            agent._execute_tool("search_profiles", {"query": "ml engineers"})
        assert agent._last_candidate_count == 3

    def test_execute_sql_sets_count(self):
        """execute_sql sets _last_candidate_count to number of rows."""
        agent = _make_agent()
        mock_result = {"columns": ["id"], "rows": [["cp_1"], ["cp_2"]]}
        with patch("linkedout.intelligence.agents.search_agent.execute_sql", return_value=mock_result):
            agent._execute_tool("execute_sql", {"query": "SELECT id FROM cp"})
        assert agent._last_candidate_count == 2

    def test_find_intro_paths_sets_count(self):
        """find_intro_paths sets _last_candidate_count to number of paths."""
        agent = _make_agent()
        mock_result = {"paths": [{"profile_id": "cp_1"}, {"profile_id": "cp_2"}]}
        with patch("linkedout.intelligence.agents.search_agent.find_intro_paths", return_value=mock_result):
            agent._execute_tool("find_intro_paths", {"target": "Acme Corp"})
        assert agent._last_candidate_count == 2

    def test_non_result_tool_keeps_count_zero(self):
        """Non-result-producing tools (e.g., web_search) don't set _last_candidate_count."""
        agent = _make_agent()
        agent._last_candidate_count = 0
        with patch("linkedout.intelligence.agents.search_agent.web_search", return_value="{}"):
            agent._execute_tool("web_search", {"query": "test"})
        assert agent._last_candidate_count == 0


# ── Streaming tests ──────────────────────────────────────────────────────────


def _make_llm_response(content: str = "", tool_calls: list | None = None):
    """Create a mock LLM response object."""
    resp = MagicMock()
    resp.content = content
    resp.tool_calls = tool_calls or []
    resp.has_tool_calls = bool(tool_calls)
    return resp


class TestRunStreaming:
    """Tests for run_streaming buffer-then-emit behaviour."""

    def _collect_events(self, agent, query: str) -> list[SearchEvent]:
        """Run run_streaming and collect all emitted events."""
        events = []

        async def _run():
            async for event in agent.run_streaming(query):
                events.append(event)

        asyncio.get_event_loop().run_until_complete(_run())
        return events

    def test_emits_single_results_event_not_individual(self):
        """run_streaming emits one type=results event (batch), never type=result (individual)."""
        agent = _make_agent()

        sql_result = json.dumps({
            "columns": ["crawled_profile_id", "full_name"],
            "rows": [["cp_A", "Alice"], ["cp_B", "Bob"]],
        })

        # LLM call 1: tool call to execute_sql
        # LLM call 2: final answer (no tool calls)
        responses = [
            _make_llm_response(tool_calls=[{
                "id": "tc_1", "name": "execute_sql",
                "args": {"query": "SELECT crawled_profile_id, full_name FROM cp"},
            }]),
            _make_llm_response(content="Found Alice and Bob."),
        ]

        with patch.object(agent, "_create_llm_client") as mock_llm, \
             patch("linkedout.intelligence.agents.search_agent.execute_sql", return_value=json.loads(sql_result)):
            client = MagicMock()
            client.call_llm_with_tools.side_effect = responses
            mock_llm.return_value = client

            events = self._collect_events(agent, "find people")

        event_types = [e.type for e in events]
        assert "results" in event_types, "Should emit a batch 'results' event"
        assert "result" not in event_types, "Should NOT emit individual 'result' events"

        # Verify the results payload contains ordered items
        results_event = next(e for e in events if e.type == "results")
        items = results_event.payload["items"]
        assert len(items) == 2
        assert items[0]["crawled_profile_id"] == "cp_A"
        assert items[1]["crawled_profile_id"] == "cp_B"

    def test_results_event_respects_declared_order(self):
        """Batch results event honours set_result_order declared ordering."""
        agent = _make_agent()

        sql_result = json.dumps({
            "columns": ["crawled_profile_id", "full_name"],
            "rows": [["cp_A", "Alice"], ["cp_B", "Bob"], ["cp_C", "Carol"]],
        })
        # LLM call 1: execute_sql
        # LLM call 2: set_result_order (reorder: C, A, B)
        # LLM call 3: final answer
        responses = [
            _make_llm_response(tool_calls=[{
                "id": "tc_1", "name": "execute_sql",
                "args": {"query": "SELECT crawled_profile_id, full_name FROM cp"},
            }]),
            _make_llm_response(tool_calls=[{
                "id": "tc_2", "name": "set_result_order",
                "args": {"profile_ids": ["cp_C", "cp_A", "cp_B"]},
            }]),
            _make_llm_response(content="Here are the results."),
        ]

        with patch.object(agent, "_create_llm_client") as mock_llm, \
             patch("linkedout.intelligence.agents.search_agent.execute_sql", return_value=json.loads(sql_result)):
            client = MagicMock()
            client.call_llm_with_tools.side_effect = responses
            mock_llm.return_value = client

            events = self._collect_events(agent, "find people")

        results_event = next(e for e in events if e.type == "results")
        ids = [item["crawled_profile_id"] for item in results_event.payload["items"]]
        assert ids == ["cp_C", "cp_A", "cp_B"]

    def test_progress_message_uses_candidate_count(self):
        """Progress thinking event uses _last_candidate_count (C4 pattern), not JSON parsing."""
        agent = _make_agent()

        sql_result = json.dumps({
            "columns": ["crawled_profile_id", "full_name"],
            "rows": [["cp_A", "Alice"], ["cp_B", "Bob"], ["cp_C", "Carol"]],
        })

        responses = [
            _make_llm_response(tool_calls=[{
                "id": "tc_1", "name": "execute_sql",
                "args": {"query": "SELECT crawled_profile_id, full_name FROM cp"},
            }]),
            _make_llm_response(content="Done."),
        ]

        with patch.object(agent, "_create_llm_client") as mock_llm, \
             patch("linkedout.intelligence.agents.search_agent.execute_sql", return_value=json.loads(sql_result)):
            client = MagicMock()
            client.call_llm_with_tools.side_effect = responses
            mock_llm.return_value = client

            events = self._collect_events(agent, "find people")

        thinking_events = [e for e in events if e.type == "thinking"]
        progress_msgs = [e.message for e in thinking_events if "candidates" in (e.message or "")]
        assert any("3 candidates" in msg for msg in progress_msgs), \
            f"Expected '3 candidates' in progress messages, got: {progress_msgs}"

    def test_done_event_has_correct_total(self):
        """Done event total matches the batch results count."""
        agent = _make_agent()

        sql_result = json.dumps({
            "columns": ["crawled_profile_id", "full_name"],
            "rows": [["cp_A", "Alice"]],
        })

        responses = [
            _make_llm_response(tool_calls=[{
                "id": "tc_1", "name": "execute_sql",
                "args": {"query": "SELECT crawled_profile_id, full_name FROM cp"},
            }]),
            _make_llm_response(content="Found Alice."),
        ]

        with patch.object(agent, "_create_llm_client") as mock_llm, \
             patch("linkedout.intelligence.agents.search_agent.execute_sql", return_value=json.loads(sql_result)):
            client = MagicMock()
            client.call_llm_with_tools.side_effect = responses
            mock_llm.return_value = client

            events = self._collect_events(agent, "find Alice")

        done_event = next(e for e in events if e.type == "done")
        assert done_event.payload["total"] == 1
        assert done_event.payload["answer"] == "Found Alice."

    def test_no_results_emits_empty_batch(self):
        """When no search tools are called, results event has empty items list."""
        agent = _make_agent()

        # LLM answers directly without tool calls
        responses = [
            _make_llm_response(content="I can help with that. What are you looking for?"),
        ]

        with patch.object(agent, "_create_llm_client") as mock_llm:
            client = MagicMock()
            client.call_llm_with_tools.side_effect = responses
            mock_llm.return_value = client

            events = self._collect_events(agent, "hello")

        results_event = next(e for e in events if e.type == "results")
        assert results_event.payload["items"] == []

        done_event = next(e for e in events if e.type == "done")
        assert done_event.payload["total"] == 0
