# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ConversationManager."""

from unittest.mock import MagicMock

import pytest

from utilities.llm_manager.conversation_manager import ConversationManager, SummaryResult


def _make_turn(
    user_query: str,
    transcript: list | None = None,
    summary: str | None = None,
) -> dict:
    """Helper to build a turn dict."""
    return {
        "user_query": user_query,
        "transcript": transcript,
        "summary": summary,
    }


def _make_transcript(assistant_content: str) -> list:
    return [{"role": "assistant", "content": assistant_content}]


@pytest.fixture()
def mock_llm_client():
    client = MagicMock()
    client.call_llm.return_value = "Generated summary of older turns"
    return client


@pytest.fixture()
def manager(mock_llm_client):
    return ConversationManager(
        llm_client=mock_llm_client,
        summarization_prompt="Summarize the conversation.",
        recent_turns=4,
    )


class TestFewTurnsNoSummarization:
    """When turns <= recent_turns, all are returned verbatim with no LLM call."""

    def test_single_turn(self, manager, mock_llm_client):
        turns = [_make_turn("find ML engineers")]
        result = manager.build_history(turns)

        assert isinstance(result, SummaryResult)
        assert len(result.messages) == 1
        assert result.messages[0] == {"role": "user", "content": "find ML engineers"}
        assert result.generated_summaries == {}
        mock_llm_client.call_llm.assert_not_called()

    def test_exactly_four_turns(self, manager, mock_llm_client):
        turns = [
            _make_turn("query 1", _make_transcript("answer 1")),
            _make_turn("query 2", _make_transcript("answer 2")),
            _make_turn("query 3", _make_transcript("answer 3")),
            _make_turn("query 4", _make_transcript("answer 4")),
        ]
        result = manager.build_history(turns)

        # 4 user + 4 assistant = 8 messages
        assert len(result.messages) == 8
        assert result.generated_summaries == {}
        mock_llm_client.call_llm.assert_not_called()

    def test_empty_turns(self, manager, mock_llm_client):
        result = manager.build_history([])
        assert result.messages == []
        mock_llm_client.call_llm.assert_not_called()


class TestManyTurnsSummarization:
    """When turns > recent_turns, older turns get summarized."""

    def test_five_turns_summarizes_first(self, manager, mock_llm_client):
        turns = [
            _make_turn("old query", _make_transcript("old answer")),
            _make_turn("query 2", _make_transcript("answer 2")),
            _make_turn("query 3", _make_transcript("answer 3")),
            _make_turn("query 4", _make_transcript("answer 4")),
            _make_turn("query 5", _make_transcript("answer 5")),
        ]
        result = manager.build_history(turns)

        # 1 summary message + 4 recent * 2 (user+assistant) = 9
        assert len(result.messages) == 9
        assert "[Previous conversation summary]" in result.messages[0]["content"]
        assert result.messages[0]["role"] == "assistant"
        mock_llm_client.call_llm.assert_called_once()

    def test_recent_turns_preserved_verbatim(self, manager, mock_llm_client):
        turns = [
            _make_turn("old query"),
            _make_turn("recent 1", _make_transcript("ans 1")),
            _make_turn("recent 2", _make_transcript("ans 2")),
            _make_turn("recent 3", _make_transcript("ans 3")),
            _make_turn("recent 4", _make_transcript("ans 4")),
        ]
        result = manager.build_history(turns)

        # Skip summary message, check recent turns
        recent_messages = result.messages[1:]
        user_messages = [m for m in recent_messages if m["role"] == "user"]
        assert [m["content"] for m in user_messages] == [
            "recent 1", "recent 2", "recent 3", "recent 4"
        ]


class TestCachedSummaryUsed:
    """When turn.summary exists, no LLM call is made for that turn."""

    def test_all_older_cached(self, manager, mock_llm_client):
        turns = [
            _make_turn("old 1", summary="cached summary 1"),
            _make_turn("old 2", summary="cached summary 2"),
            _make_turn("recent 1", _make_transcript("ans 1")),
            _make_turn("recent 2", _make_transcript("ans 2")),
            _make_turn("recent 3", _make_transcript("ans 3")),
            _make_turn("recent 4", _make_transcript("ans 4")),
        ]
        result = manager.build_history(turns)

        mock_llm_client.call_llm.assert_not_called()
        assert "cached summary 1" in result.messages[0]["content"]
        assert "cached summary 2" in result.messages[0]["content"]
        assert result.generated_summaries == {}

    def test_partial_cached(self, manager, mock_llm_client):
        """Some older turns cached, some not -- LLM called only for uncached."""
        turns = [
            _make_turn("old 1", summary="cached summary"),
            _make_turn("old 2"),  # no summary -- needs LLM
            _make_turn("recent 1", _make_transcript("ans 1")),
            _make_turn("recent 2", _make_transcript("ans 2")),
            _make_turn("recent 3", _make_transcript("ans 3")),
            _make_turn("recent 4", _make_transcript("ans 4")),
        ]
        result = manager.build_history(turns)

        mock_llm_client.call_llm.assert_called_once()
        assert result.generated_summaries == {1: "Generated summary of older turns"}


class TestSummaryGeneratedWhenMissing:
    """When turn.summary is None, LLM is called to generate one."""

    def test_generated_summary_in_result(self, manager, mock_llm_client):
        turns = [
            _make_turn("old query", _make_transcript("old answer")),
            _make_turn("recent 1"),
            _make_turn("recent 2"),
            _make_turn("recent 3"),
            _make_turn("recent 4"),
        ]
        result = manager.build_history(turns)

        assert 0 in result.generated_summaries
        assert result.generated_summaries[0] == "Generated summary of older turns"
        mock_llm_client.call_llm.assert_called_once()

    def test_summarization_prompt_passed_to_llm(self, manager, mock_llm_client):
        turns = [
            _make_turn("old query"),
            _make_turn("recent 1"),
            _make_turn("recent 2"),
            _make_turn("recent 3"),
            _make_turn("recent 4"),
        ]
        manager.build_history(turns)

        call_args = mock_llm_client.call_llm.call_args[0][0]
        messages = call_args.get_messages()
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "Summarize the conversation."

    def test_llm_failure_fallback(self, manager, mock_llm_client):
        """On LLM failure, falls back to raw user queries."""
        mock_llm_client.call_llm.side_effect = RuntimeError("LLM down")

        turns = [
            _make_turn("old query 1"),
            _make_turn("old query 2"),
            _make_turn("recent 1"),
            _make_turn("recent 2"),
            _make_turn("recent 3"),
            _make_turn("recent 4"),
        ]
        result = manager.build_history(turns)

        # Should not raise, uses fallback
        assert "old query 1" in result.messages[0]["content"]
        assert "old query 2" in result.messages[0]["content"]


class TestCustomRecentTurns:
    """Verify the recent_turns parameter is respected."""

    def test_recent_turns_two(self, mock_llm_client):
        mgr = ConversationManager(
            llm_client=mock_llm_client,
            summarization_prompt="summarize",
            recent_turns=2,
        )
        turns = [
            _make_turn("q1"),
            _make_turn("q2"),
            _make_turn("q3"),
        ]
        result = mgr.build_history(turns)

        # 1 summary + 2 recent user messages = 3
        assert len(result.messages) == 3
        user_msgs = [m for m in result.messages if m["role"] == "user"]
        assert [m["content"] for m in user_msgs] == ["q2", "q3"]
