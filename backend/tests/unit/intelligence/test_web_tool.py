# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the web search tool."""
from unittest.mock import MagicMock, patch

import pytest

from linkedout.intelligence.tools.web_tool import MAX_WEB_SEARCHES_PER_TURN, web_search


def _make_mock_response(text_content: str):
    """Build a mock OpenAI Responses API response with message output."""
    content_block = MagicMock()
    content_block.type = "output_text"
    content_block.text = text_content

    message_item = MagicMock()
    message_item.type = "message"
    message_item.content = [content_block]

    response = MagicMock()
    response.output = [message_item]
    return response


class TestWebSearchReturnsText:
    @patch("linkedout.intelligence.tools.web_tool._get_client")
    def test_web_search_returns_text(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.responses.create.return_value = _make_mock_response(
            "Lovable AI raised $200M from Spark Capital."
        )

        result = web_search("who invested in Lovable AI")

        assert "Lovable AI" in result
        assert "200M" in result
        mock_client.responses.create.assert_called_once()


class TestWebSearchTimeout:
    @patch("linkedout.intelligence.tools.web_tool._get_client")
    def test_web_search_timeout(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.responses.create.side_effect = TimeoutError("Request timed out")

        result = web_search("slow query")

        assert "timed out" in result.lower()
        assert isinstance(result, str)


class TestWebSearchRateLimit:
    def test_web_search_rate_limit(self):
        """Verify 3-call limit per turn returns limit message on 4th call."""
        call_count = {"count": 0}

        with patch("linkedout.intelligence.tools.web_tool._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.responses.create.return_value = _make_mock_response("result")

            # First 3 calls should succeed
            for i in range(MAX_WEB_SEARCHES_PER_TURN):
                result = web_search(f"query {i}", _call_count=call_count)
                assert "limit reached" not in result.lower()

            # 4th call should be rate-limited
            result = web_search("query 4", _call_count=call_count)
            assert "limit reached" in result.lower()
            assert "3/3" in result


class TestWebSearchNetworkError:
    @patch("linkedout.intelligence.tools.web_tool._get_client")
    def test_web_search_network_error(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.responses.create.side_effect = ConnectionError("Network unreachable")

        result = web_search("some query")

        assert "failed" in result.lower()
        assert "ConnectionError" in result
        # Must not contain a stack trace
        assert "Traceback" not in result


class TestWebSearchEmptyQuery:
    def test_web_search_empty_string(self):
        result = web_search("")
        assert "error" in result.lower()
        assert "non-empty" in result.lower()

    def test_web_search_whitespace_only(self):
        result = web_search("   ")
        assert "error" in result.lower()
        assert "non-empty" in result.lower()
