# SPDX-License-Identifier: Apache-2.0
"""Tests for LLMToolResponse and SystemUser types."""

from utilities.llm_manager import LLMToolResponse, SystemUser


class TestLLMToolResponse:
    def test_default_has_no_tool_calls(self):
        response = LLMToolResponse()
        assert response.has_tool_calls is False
        assert response.content == ""

    def test_with_tool_calls(self):
        response = LLMToolResponse(
            tool_calls=[{"id": "1", "name": "search", "args": {"q": "test"}}]
        )
        assert response.has_tool_calls is True

    def test_content_preserved(self):
        response = LLMToolResponse(content="Hello world")
        assert response.content == "Hello world"

    def test_empty_tool_calls_list(self):
        response = LLMToolResponse(tool_calls=[])
        assert response.has_tool_calls is False


class TestSystemUser:
    def test_get_agent_id(self):
        user = SystemUser("search-agent")
        assert user.get_agent_id() == "search-agent"

    def test_get_session_id_returns_none(self):
        user = SystemUser("search-agent")
        assert user.get_session_id() is None
