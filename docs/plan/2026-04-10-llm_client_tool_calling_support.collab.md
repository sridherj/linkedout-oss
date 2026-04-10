# Plan: Add tool-calling support to LLMClient

## Context
`SearchAgent` and `WhyThisPersonExplainer` construct `ChatOpenAI` directly, bypassing `LangChainLLMClient`. This means no Langfuse tracing for the most important LLM calls in the app (search). The fix: extend the LLM client abstraction to support tool-calling properly, then migrate both consumers.

`LLMMessage` already supports tool messages (`add_assistant_message` with `tool_calls`, `add_tool_message`). So the building blocks exist — we just need the client method.

## Changes

### 1. `LLMToolResponse` — `src/utilities/llm_manager/llm_schemas.py`
Pydantic BaseModel (matches module convention) for tool-calling response:
```python
class LLMToolResponse(BaseModel):
    content: str = ""
    tool_calls: list[dict[str, Any]] = []  # Each: {"id": str, "name": str, "args": dict}

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)
```

### 2. `SystemUser` — `src/utilities/llm_manager/llm_client_user.py`
Lightweight `LLMClientUser` for callers that don't extend `BaseAgent`:
```python
class SystemUser(LLMClientUser):
    def __init__(self, agent_id: str):
        self._agent_id = agent_id
    def get_agent_id(self) -> str:
        return self._agent_id
    def get_session_id(self) -> Optional[str]:
        return None
```

### 3. `call_llm_with_tools()` — `src/utilities/llm_manager/llm_client.py`
Add abstract method to `LLMClient`:
```python
def call_llm_with_tools(self, message: LLMMessage, tools: list[dict]) -> LLMToolResponse
```

Implement in `LangChainLLMClient` — same pattern as `call_llm`: convert messages, `bind_tools`, invoke with callbacks, record metrics, return `LLMToolResponse`.

### 4. Refactor `SearchAgent` — `src/linkedout/intelligence/agents/search_agent.py`
- Replace `_create_llm()` with `_create_llm_client()` returning `LangChainLLMClient` via `LLMFactory`
- `run()` and `run_streaming()`: use `LLMMessage` + `call_llm_with_tools()` instead of raw LangChain messages
- `_determine_query_type()` and `_collect_results()`: adapt to walk `LLMMessage.get_messages()` dicts instead of `isinstance(msg, AIMessage)` checks
- Remove `from langchain_openai import ChatOpenAI`

### 5. Refactor `WhyThisPersonExplainer` — `src/linkedout/intelligence/explainer/why_this_person.py`
- Replace `_create_llm()` with `_create_llm_client()` returning `LangChainLLMClient` via `LLMFactory`
- `explain()`: use `LLMMessage` + `call_llm()` instead of raw `ChatOpenAI`
- Remove `from langchain_openai import ChatOpenAI`

### 6. Exports — `src/utilities/llm_manager/__init__.py`
Add `SystemUser` and `LLMToolResponse` to exports.

## Key design decisions
- **Tool loop stays in SearchAgent** — it's domain logic, not client concern
- **`LLMToolResponse`** instead of returning raw `AIMessage` — no LangChain leakage
- **`SystemUser`** instead of making user optional — explicit, no changes to interface
- **`bind_tools` per call** — cheap operation, no need to cache

## Tests — `tests/utilities/llm_manager/test_llm_client.py`
- `call_llm_with_tools` calls `bind_tools` + `invoke` with callbacks, returns `LLMToolResponse`
- `LLMToolResponse.has_tool_calls` — True when tool_calls present, False when empty
- `SystemUser` — `get_agent_id()` returns provided id, `get_session_id()` returns None

## Verification
1. Run `pytest tests/utilities/llm_manager/` — existing + new tests pass
2. Run `pytest tests/` — no regressions
3. Start local server, hit search endpoint, check Langfuse for traces
