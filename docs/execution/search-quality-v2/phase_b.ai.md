# Phase B: Add Web Search Tool

**Effort:** 1 session
**Dependencies:** None (can start in parallel with A)
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Give the search agent web search capability by implementing `web_search` as a regular function tool. The spike (`./tmp_spike_web_search.py`) validated this approach — zero prompt engineering + web search = Claude Code quality.

## What to Do

### 1. Create web search tool

**NEW file:** `./src/linkedout/intelligence/tools/web_tool.py`

Implementation:
- Function `web_search(query: str) -> str`
- Delegates to OpenAI Responses API with `web_search_preview` tool on `gpt-4.1-mini`
- 10-second timeout on the OpenAI client
- Returns extracted text from response
- Handles errors gracefully (return error message, don't raise)

Reference the spike for the working implementation pattern:
```bash
cat ./tmp_spike_web_search.py
```

### 2. Register in search agent

**File:** `./src/linkedout/intelligence/agents/search_agent.py`

Add to `_TOOL_DEFINITIONS`:
```python
{
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the internet for context not in the database — "
                       "company info, investors, funding details, industry context, "
                       "recent news, executive teams.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"],
        },
    },
}
```

Add dispatch in `_execute_tool()`:
```python
elif tool_name == "web_search":
    return web_search(tool_args["query"])
```

### 3. Add per-turn web search counter

In `_execute_tool()`, add a counter that limits web search to **3 calls per turn**. After 3 calls, return:
```
"Web search limit reached for this turn (3/3). Work with the information you already have."
```

Reset the counter at the start of each `run()` call.

### 4. Add Langfuse instrumentation

Wrap the web search call with a Langfuse span (follow the pattern used by `sql_tool.py` and `vector_tool.py`). Include:
- Input: the search query
- Output: the search result (truncated if very long)
- Duration

### 5. Create unit tests

**NEW file:** `./tests/unit/intelligence/test_web_tool.py`

Test cases:
- `test_web_search_returns_text` — mock OpenAI client, verify text extraction
- `test_web_search_timeout` — mock timeout, verify graceful error message
- `test_web_search_rate_limit` — verify 3-call limit per turn returns limit message
- `test_web_search_network_error` — mock network error (ConnectionError/RequestException), verify returns graceful error message (not a stack trace)
- `test_web_search_empty_query` — pass empty string or None as query, verify returns validation error message

### 6. Create integration test

**NEW file:** `tests/integration/linkedout/intelligence/test_web_search_integration.py`

Live web search integration test:
- Marked `@pytest.mark.live_llm` (skipped in CI)
- Calls `web_search()` with a real query (e.g., "who invested in Lovable AI")
- Verifies OpenAI Responses API returns non-empty results
- Verifies result is a string with meaningful content (len > 50)

## Verification

```bash
# Unit tests
pytest tests/unit/intelligence/test_web_tool.py -v
pytest tests/unit/intelligence/ -v

# Integration test (live, skipped in CI)
pytest tests/integration/linkedout/intelligence/test_web_search_integration.py -v -m live_llm

# Manual smoke test (requires OpenAI API key)
python -c "
from linkedout.intelligence.tools.web_tool import web_search
result = web_search('who invested in Lovable AI')
print(result[:500])
assert len(result) > 50, 'Result too short'
print('OK: web search works')
"
```

### Verification gate (all must pass)

- Successful web search returns extracted text
- 4th call in same turn returns "limit reached" message
- Timeout after 10s returns graceful error
- **Network error returns graceful error (not stack trace)**
- **Empty/null query returns validation error**
- **Live integration test passes** (`-m live_llm`)

## Expected Impact

+0.5-1.0 average across 10-15 queries that need external context (investors, company info, industry context, "impressive" assessments).
