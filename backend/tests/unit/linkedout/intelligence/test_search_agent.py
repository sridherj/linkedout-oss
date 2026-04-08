# SPDX-License-Identifier: Apache-2.0
"""Unit tests for SearchAgent with mocked LLM and tools."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from linkedout.intelligence.agents.search_agent import (
    MAX_ITERATIONS,
    SearchAgent,
    _rows_to_result_items,
    _sql_rows_to_result_items,
)
from linkedout.intelligence.contracts import SearchResponse
from utilities.llm_manager import LLMToolResponse


@pytest.fixture()
def mock_session():
    return MagicMock()


@pytest.fixture()
def agent(mock_session):
    with patch(
        "linkedout.intelligence.agents.search_agent.build_schema_context",
        return_value="-- schema --",
    ):
        return SearchAgent(session=mock_session, app_user_id="usr_test_001")


def _make_tool_call_response(tool_name: str, tool_args: dict, call_id: str = "call_1") -> LLMToolResponse:
    """Create an LLMToolResponse with a tool call."""
    return LLMToolResponse(
        content="",
        tool_calls=[{"id": call_id, "name": tool_name, "args": tool_args}],
    )


def _make_final_response(text: str) -> LLMToolResponse:
    return LLMToolResponse(content=text, tool_calls=[])


class TestToolRouting:
    """Verify the LLM's tool calls get dispatched correctly."""

    def test_structured_query_routes_to_sql(self, agent):
        """A structured query should invoke execute_sql."""
        sql_response = _make_tool_call_response(
            "execute_sql",
            {"query": "SELECT full_name FROM crawled_profile cp JOIN connection c ON c.crawled_profile_id = cp.id WHERE c.app_user_id = :app_user_id"},
        )
        final_response = _make_final_response("Found 3 people at Google.")

        with (
            patch.object(agent, "_create_llm_client") as mock_client_factory,
            patch(
                "linkedout.intelligence.agents.search_agent.execute_sql",
                return_value={"columns": ["full_name"], "rows": [["Alice"]], "row_count": 1},
            ) as mock_sql,
        ):
            mock_client = MagicMock()
            mock_client.call_llm_with_tools.side_effect = [sql_response, final_response]
            mock_client_factory.return_value = mock_client

            result = agent.run("Who works at Google?")

            mock_sql.assert_called_once()
            assert result.query_type == "sql"
            assert "Found 3 people" in result.answer

    def test_semantic_query_routes_to_vector(self, agent):
        """A semantic query should invoke search_profiles."""
        vector_response = _make_tool_call_response(
            "search_profiles",
            {"query": "AI agents researcher"},
        )
        final_response = _make_final_response("Found people working on AI agents.")

        with (
            patch.object(agent, "_create_llm_client") as mock_client_factory,
            patch(
                "linkedout.intelligence.agents.search_agent.search_profiles",
                return_value=[
                    {
                        "id": "cp_1",
                        "full_name": "Bob",
                        "headline": "AI Researcher",
                        "current_position": None,
                        "current_company_name": None,
                        "location_city": None,
                        "location_country": None,
                        "linkedin_url": None,
                        "public_identifier": None,
                        "connection_id": "conn_1",
                        "affinity_score": 50.0,
                        "dunbar_tier": "active",
                        "connected_at": "2024-01-15",
                        "has_enriched_data": True,
                        "similarity": 0.92,
                    }
                ],
            ) as mock_vector,
        ):
            mock_client = MagicMock()
            mock_client.call_llm_with_tools.side_effect = [vector_response, final_response]
            mock_client_factory.return_value = mock_client

            result = agent.run("People working on AI agents")

            mock_vector.assert_called_once()
            assert result.query_type == "vector"
            assert len(result.results) == 1
            assert result.results[0].full_name == "Bob"
            assert result.results[0].similarity_score == 0.92


class TestIterationLoop:
    """Verify the tool-calling loop respects MAX_ITERATIONS."""

    def test_max_iterations_enforced(self, agent):
        """Agent should stop after MAX_ITERATIONS even if LLM keeps calling tools."""
        tool_call = _make_tool_call_response("execute_sql", {"query": "SELECT 1"})

        with (
            patch.object(agent, "_create_llm_client") as mock_client_factory,
            patch(
                "linkedout.intelligence.agents.search_agent.execute_sql",
                return_value={"columns": ["x"], "rows": [[1]], "row_count": 1},
            ),
        ):
            mock_client = MagicMock()
            # Always return tool calls, never a final answer
            mock_client.call_llm_with_tools.return_value = tool_call
            mock_client_factory.return_value = mock_client

            result = agent.run("loop forever")

            assert mock_client.call_llm_with_tools.call_count == MAX_ITERATIONS
            assert isinstance(result, SearchResponse)


class TestErrorRecovery:
    """Test retry with schema hint on column-not-found."""

    def test_sql_error_with_hint_returned_to_llm(self, agent):
        """When SQL fails with a hint, the error+hint is returned so LLM can self-correct."""
        # First call: LLM generates bad SQL
        bad_sql_call = _make_tool_call_response(
            "execute_sql",
            {"query": "SELECT bad_column FROM crawled_profile"},
            call_id="call_bad",
        )
        # Second call: LLM fixes the SQL
        good_sql_call = _make_tool_call_response(
            "execute_sql",
            {"query": "SELECT full_name FROM crawled_profile cp JOIN connection c ON c.crawled_profile_id = cp.id WHERE c.app_user_id = :app_user_id"},
            call_id="call_good",
        )
        final_response = _make_final_response("Found the data.")

        error_result = {
            "error": 'column "bad_column" does not exist',
            "hint": "Available columns in 'crawled_profile': id, full_name, headline",
            "columns": [],
            "rows": [],
            "row_count": 0,
        }
        good_result = {"columns": ["full_name"], "rows": [["Alice"]], "row_count": 1}

        with (
            patch.object(agent, "_create_llm_client") as mock_client_factory,
            patch(
                "linkedout.intelligence.agents.search_agent.execute_sql",
                side_effect=[error_result, good_result],
            ),
        ):
            mock_client = MagicMock()
            mock_client.call_llm_with_tools.side_effect = [bad_sql_call, good_sql_call, final_response]
            mock_client_factory.return_value = mock_client

            result = agent.run("Find people")

            assert result.answer == "Found the data."
            assert result.query_type == "sql"


class TestResponseMapping:
    """Test that results map correctly to SearchResponse."""

    def test_search_response_fields(self, agent):
        """Final response has all expected fields."""
        final_response = _make_final_response("No tool calls needed.")

        with patch.object(agent, "_create_llm_client") as mock_client_factory:
            mock_client = MagicMock()
            mock_client.call_llm_with_tools.return_value = final_response
            mock_client_factory.return_value = mock_client

            result = agent.run("Hello")

            assert isinstance(result, SearchResponse)
            assert result.answer == "No tool calls needed."
            assert result.query_type == "direct"
            assert result.result_count == 0
            assert result.results == []


class TestResultItemConverters:
    """Test the row-to-SearchResultItem helper functions."""

    def test_rows_to_result_items(self):
        rows = [
            {
                "id": "cp_1",
                "connection_id": "conn_1",
                "full_name": "Alice",
                "headline": "Engineer",
                "current_position": "SWE",
                "current_company_name": "Acme",
                "location_city": "SF",
                "location_country": "US",
                "linkedin_url": "https://linkedin.com/in/alice",
                "public_identifier": "alice",
                "affinity_score": 75.0,
                "dunbar_tier": "active",
                "connected_at": "2024-06-01",
                "has_enriched_data": True,
                "similarity": 0.88,
            }
        ]
        items = _rows_to_result_items(rows)
        assert len(items) == 1
        assert items[0].full_name == "Alice"
        assert items[0].similarity_score == 0.88

    def test_sql_rows_to_result_items(self):
        columns = ["connection_id", "full_name", "headline"]
        rows = [["conn_1", "Bob", "PM"]]
        items = _sql_rows_to_result_items(columns, rows)
        assert len(items) == 1
        assert items[0].full_name == "Bob"
        assert items[0].headline == "PM"
        assert items[0].connection_id == "conn_1"


class TestCollectResultsDedup:
    """Test that _collect_results deduplicates by crawled_profile_id / connection_id."""

    def test_dedup_by_crawled_profile_id(self, agent):
        """Same person from SQL + vector tools should appear only once (first occurrence kept)."""
        sql_result = json.dumps({
            "columns": ["connection_id", "crawled_profile_id", "full_name", "headline"],
            "rows": [
                ["conn_1", "cp_1", "Alice (SQL)", "Engineer"],
                ["conn_2", "cp_2", "Bob", "PM"],
            ],
            "row_count": 2,
        })
        vector_result = json.dumps([
            {
                "id": "cp_1", "connection_id": "conn_1",
                "full_name": "Alice (Vector)", "headline": "Engineer",
                "current_position": None, "current_company_name": None,
                "location_city": None, "location_country": None,
                "linkedin_url": None, "public_identifier": None,
                "affinity_score": None, "dunbar_tier": None,
                "connected_at": None, "has_enriched_data": False,
                "similarity": 0.95,
            },
            {
                "id": "cp_3", "connection_id": "conn_3",
                "full_name": "Charlie", "headline": "Designer",
                "current_position": None, "current_company_name": None,
                "location_city": None, "location_country": None,
                "linkedin_url": None, "public_identifier": None,
                "affinity_score": None, "dunbar_tier": None,
                "connected_at": None, "has_enriched_data": False,
                "similarity": 0.80,
            },
        ])

        messages = [
            {"role": "assistant", "content": "", "tool_calls": [{"id": "call_sql", "name": "execute_sql", "args": {"query": "SELECT ..."}}]},
            {"role": "tool", "content": sql_result, "tool_call_id": "call_sql"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "call_vec", "name": "search_profiles", "args": {"query": "test"}}]},
            {"role": "tool", "content": vector_result, "tool_call_id": "call_vec"},
        ]

        results = agent._collect_results(messages)
        assert len(results) == 3
        names = [r.full_name for r in results]
        assert names == ["Alice (SQL)", "Bob", "Charlie"]

    def test_dedup_fallback_to_connection_id(self, agent):
        """When crawled_profile_id is empty, dedup by connection_id."""
        sql_result = json.dumps({
            "columns": ["connection_id", "full_name"],
            "rows": [
                ["conn_1", "Alice"],
                ["conn_1", "Alice Duplicate"],
            ],
            "row_count": 2,
        })

        messages = [
            {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1", "name": "execute_sql", "args": {"query": "SELECT ..."}}]},
            {"role": "tool", "content": sql_result, "tool_call_id": "call_1"},
        ]

        results = agent._collect_results(messages)
        assert len(results) == 1
        assert results[0].full_name == "Alice"


class TestRetrySimplification:
    """Verify _execute_tool_with_retry returns errors (with hints) for LLM self-correction."""

    def test_error_with_hint_returned_not_swallowed(self, agent):
        """SQL error with hint should be returned as-is so the LLM can see it."""
        error_result = {
            "error": 'column "bad_col" does not exist',
            "hint": "Available columns: id, full_name, headline",
            "columns": [],
            "rows": [],
            "row_count": 0,
        }

        with patch.object(agent, "_execute_tool", return_value=json.dumps(error_result)):
            result_str = agent._execute_tool_with_retry("execute_sql", {"query": "SELECT bad_col"})

        result = json.loads(result_str)
        assert result["error"] == 'column "bad_col" does not exist'
        assert result["hint"] == "Available columns: id, full_name, headline"

    def test_success_returned_directly(self, agent):
        """Successful result should be returned as-is."""
        good_result = {"columns": ["full_name"], "rows": [["Alice"]], "row_count": 1}

        with patch.object(agent, "_execute_tool", return_value=json.dumps(good_result)):
            result_str = agent._execute_tool_with_retry("execute_sql", {"query": "SELECT full_name"})

        result = json.loads(result_str)
        assert result["row_count"] == 1


class TestConversationHistory:
    """Test that turn history is injected via ConversationManager."""

    def test_run_with_turn_history(self, agent):
        """run() should accept turn_history and inject it via ConversationManager."""
        final_response = _make_final_response("Narrowed to Bangalore.")

        with (
            patch.object(agent, "_create_llm_client") as mock_client_factory,
            patch.object(agent, "_create_conversation_manager") as mock_conv_factory,
        ):
            mock_client = MagicMock()
            mock_client.call_llm_with_tools.return_value = final_response
            mock_client_factory.return_value = mock_client

            mock_conv_manager = MagicMock()
            mock_conv_manager.build_history.return_value = MagicMock(
                messages=[
                    {"role": "user", "content": "find ML engineers"},
                    {"role": "assistant", "content": "Found 10 ML engineers."},
                ]
            )
            mock_conv_factory.return_value = mock_conv_manager

            turn_history = [
                {"user_query": "find ML engineers", "transcript": [], "summary": None},
            ]
            result = agent.run("only in Bangalore", turn_history=turn_history)

            mock_conv_manager.build_history.assert_called_once_with(turn_history)
            assert result.answer == "Narrowed to Bangalore."
