# SPDX-License-Identifier: Apache-2.0
"""Web search tool for SearchAgent — delegates to OpenAI Responses API."""
import time

from shared.utilities.langfuse_guard import observe
from openai import OpenAI

from shared.config import get_config
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")

_MODEL = "gpt-4.1-mini"
_TIMEOUT_SECONDS = 10
MAX_WEB_SEARCHES_PER_TURN = 3


def _get_client() -> OpenAI:
    """Create an OpenAI client with timeout configured."""
    settings = get_config()
    api_key = settings.openai_api_key or settings.llm_api_key
    return OpenAI(api_key=api_key, timeout=_TIMEOUT_SECONDS)


@observe(name="web_search")
def web_search(query: str, _call_count: dict | None = None) -> str:
    """Search the internet via OpenAI Responses API with web_search_preview tool.

    Args:
        query: Search query string.
        _call_count: Optional mutable dict with 'count' key for per-turn rate limiting.
                     Managed by SearchAgent; callers outside the agent can ignore this.

    Returns:
        Extracted text from web search results, or an error message on failure.
    """
    if not query or not query.strip():
        return "Error: query must be a non-empty string."

    # Rate limit check
    if _call_count is not None:
        if _call_count.get("count", 0) >= MAX_WEB_SEARCHES_PER_TURN:
            return "Web search limit reached for this turn (3/3). Work with the information you already have."
        _call_count["count"] = _call_count.get("count", 0) + 1

    t0 = time.perf_counter()
    try:
        client = _get_client()
        resp = client.responses.create(
            model=_MODEL,
            tools=[{"type": "web_search_preview"}],
            input=f"Search the web and return factual information about: {query}. Return only facts, no commentary.",
        )

        text_parts = []
        for item in resp.output:
            if item.type == "message":
                for content in item.content:
                    if hasattr(content, "text"):
                        text_parts.append(content.text)

        result = "\n".join(text_parts) if text_parts else "No results found"
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        logger.info(f"Web search OK in {elapsed_ms}ms ({len(result)} chars): {query[:100]}")
        return result

    except TimeoutError:
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        logger.warning(f"Web search timed out after {elapsed_ms}ms: {query[:100]}")
        return "Web search timed out. Try a more specific query or work with existing information."
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        logger.error(f"Web search failed in {elapsed_ms}ms: {type(e).__name__}: {e}")
        return f"Web search failed: {type(e).__name__}. Try a different query or work with existing information."
