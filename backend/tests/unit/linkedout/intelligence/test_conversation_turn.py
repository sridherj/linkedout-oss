# SPDX-License-Identifier: Apache-2.0
"""Unit tests for SearchAgent.run_turn() — conversational search with ConversationManager."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from linkedout.intelligence.agents.search_agent import SearchAgent
from linkedout.intelligence.contracts import ConversationTurnResponse
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
        return SearchAgent(
            session=mock_session,
            app_user_id="usr_test_001",
            session_id="ss_test_001",
            tenant_id="t_001",
            bu_id="bu_001",
        )


def _make_tool_call(name: str, args: dict, call_id: str = "call_1") -> LLMToolResponse:
    return LLMToolResponse(
        content="",
        tool_calls=[{"id": call_id, "name": name, "args": args}],
    )


def _make_final(text: str) -> LLMToolResponse:
    return LLMToolResponse(content=text, tool_calls=[])


class TestRunTurnBasic:
    def test_returns_conversation_turn_response(self, agent):
        """run_turn should return a ConversationTurnResponse."""
        with patch.object(agent, "_create_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.call_llm_with_tools.return_value = _make_final("Here are some results.")
            mock_factory.return_value = mock_client

            result = agent.run_turn("find ML engineers")

            assert isinstance(result, ConversationTurnResponse)
            assert result.message == "Here are some results."
            assert result.query_type is not None

    def test_facets_computed_from_sql_results(self, agent):
        """Response should include computed facets from SQL result set."""
        sql_data = {
            "columns": ["crawled_profile_id", "full_name", "location_city", "dunbar_tier"],
            "rows": [
                ["cp_1", "Alice", "Bangalore", "active"],
                ["cp_2", "Bob", "SF", "active"],
            ],
            "row_count": 2,
        }
        sql_response = _make_tool_call("execute_sql", {"query": "SELECT ..."})
        final_response = _make_final("Found 2 people.")

        with (
            patch.object(agent, "_create_llm_client") as mock_factory,
            patch(
                "linkedout.intelligence.agents.search_agent.execute_sql",
                return_value=sql_data,
            ),
        ):
            mock_client = MagicMock()
            mock_client.call_llm_with_tools.side_effect = [sql_response, final_response]
            mock_factory.return_value = mock_client

            result = agent.run_turn("who works at Google?")

            assert isinstance(result.facets, list)


class TestConversationManagerIntegration:
    def test_turn_history_injected_via_conversation_manager(self, agent):
        """run_turn with turn_history should use ConversationManager."""
        with (
            patch.object(agent, "_create_llm_client") as mock_factory,
            patch.object(agent, "_create_conversation_manager") as mock_conv_factory,
        ):
            mock_client = MagicMock()
            mock_client.call_llm_with_tools.return_value = _make_final("Filtered to 5.")
            mock_factory.return_value = mock_client

            mock_conv_manager = MagicMock()
            mock_conv_manager.build_history.return_value = MagicMock(
                messages=[
                    {"role": "user", "content": "find ML people"},
                    {"role": "assistant", "content": "Found 10 ML engineers."},
                ]
            )
            mock_conv_factory.return_value = mock_conv_manager

            turn_history = [
                {"user_query": "find ML people", "transcript": [], "summary": None},
            ]
            result = agent.run_turn("only in Bangalore", turn_history=turn_history)

            mock_conv_manager.build_history.assert_called_once_with(turn_history)
            assert result.message == "Filtered to 5."

    def test_no_turn_history_skips_conversation_manager(self, agent):
        """run_turn without turn_history should not create ConversationManager."""
        with (
            patch.object(agent, "_create_llm_client") as mock_factory,
            patch.object(agent, "_create_conversation_manager") as mock_conv_factory,
        ):
            mock_client = MagicMock()
            mock_client.call_llm_with_tools.return_value = _make_final("OK")
            mock_factory.return_value = mock_client

            result = agent.run_turn("find engineers")

            mock_conv_factory.assert_not_called()
            assert result.message == "OK"


class TestResultSummaryChips:
    def test_results_produce_count_chip(self, agent):
        """Having results should produce a count chip."""
        sql_data = {
            "columns": ["connection_id", "crawled_profile_id", "full_name"],
            "rows": [["conn_1", "cp_1", "Alice"]],
            "row_count": 1,
        }
        sql_response = _make_tool_call("execute_sql", {"query": "SELECT ..."})
        final_response = _make_final("Found Alice.")

        with (
            patch.object(agent, "_create_llm_client") as mock_factory,
            patch(
                "linkedout.intelligence.agents.search_agent.execute_sql",
                return_value=sql_data,
            ),
        ):
            mock_client = MagicMock()
            mock_client.call_llm_with_tools.side_effect = [sql_response, final_response]
            mock_factory.return_value = mock_client

            result = agent.run_turn("find Alice")

            chip_types = {c.type for c in result.result_summary_chips}
            assert "count" in chip_types
