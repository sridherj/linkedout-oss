# SPDX-License-Identifier: Apache-2.0
"""Integration test for web_search — calls the real OpenAI Responses API."""
import pytest

from linkedout.intelligence.tools.web_tool import web_search


@pytest.mark.live_llm
def test_web_search_returns_meaningful_content():
    """Live integration test: web_search returns real results from the internet."""
    result = web_search("who invested in Lovable AI")

    assert isinstance(result, str)
    assert len(result) > 50, f"Result too short ({len(result)} chars): {result}"
    # Should contain some factual content (not just an error)
    assert "failed" not in result.lower()
    assert "timed out" not in result.lower()
