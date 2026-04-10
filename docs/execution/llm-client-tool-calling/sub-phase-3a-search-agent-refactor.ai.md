# Sub-Phase 3a: SearchAgent Refactor — Use LLMClient Instead of Raw ChatOpenAI

**Goal:** system-ops
**Depends on:** SP-2 (call_llm_with_tools must exist on LangChainLLMClient)
**Estimated effort:** 1 session (~2h)
**Source plan section:** Change 4

---

## Objective

Refactor `SearchAgent` to use `LangChainLLMClient` (via `LLMFactory`) instead of constructing `ChatOpenAI` directly. This brings all SearchAgent LLM calls under Langfuse tracing. The tool-calling loop logic stays in SearchAgent — only the LLM interaction layer changes.

## Context

- `SearchAgent` is at `src/linkedout/intelligence/agents/search_agent.py`.
- It currently imports `ChatOpenAI` from `langchain_openai` and constructs it in `_create_llm()`.
- It uses LangChain message types (`AIMessage`, `HumanMessage`, `SystemMessage`, `ToolMessage`) for the tool loop.
- After this refactor, it will use `LLMMessage` for message construction and `call_llm_with_tools()` for LLM calls.
- The tool loop (iterating over tool calls, dispatching to `execute_sql`/`search_profiles`, feeding results back) stays in SearchAgent — this is domain logic.
- `SystemUser("search-agent")` provides the `LLMClientUser` identity (from SP-1).

## Tasks

1. **Replace imports:**
   - Remove: `from langchain_openai import ChatOpenAI`
   - Remove: `from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage`
   - Add: `from utilities.llm_manager import LLMFactory, LLMMessage, SystemUser, LLMToolResponse`
   - Add: `from utilities.llm_manager.llm_schemas import LLMConfig, LLMProvider`

2. **Replace `_create_llm()` with `_create_llm_client()`:**
   - Current: returns `ChatOpenAI` instance
   - New: returns `LangChainLLMClient` via `LLMFactory.create_client(SystemUser("search-agent"), config)`
   - The `LLMConfig` should be constructed from the same settings (`backend_config.OPENAI_API_KEY`, `backend_config.OPENAI_MODEL` or the model currently hardcoded).

3. **Refactor `run()` method:**
   - Replace LangChain message construction with `LLMMessage`:
     - `SystemMessage(content=...)` → `msg.add_system_message(...)`
     - `HumanMessage(content=...)` → `msg.add_user_message(...)`
   - Replace `llm.bind_tools(tools).invoke(messages)` with `client.call_llm_with_tools(msg, tools)`
   - The response is now `LLMToolResponse` — use `.content` and `.tool_calls` instead of `AIMessage.content` and `AIMessage.tool_calls`
   - For the tool loop: after getting tool call results, use `msg.add_assistant_message(content, tool_calls=...)` and `msg.add_tool_message(tool_call_id, result)` to build up the conversation
   - Loop termination: check `response.has_tool_calls` instead of `isinstance(response, AIMessage) and response.tool_calls`

4. **Refactor `run_streaming()` method:**
   - This is the streaming variant. It may need to use `acall_llm_stream` or a streaming tool-call pattern.
   - If `call_llm_with_tools` doesn't support streaming natively, the approach is: use `call_llm_with_tools` for tool-calling iterations (non-streaming), then for the final text response (no tool calls), optionally stream via `acall_llm_stream`.
   - Alternatively, keep the non-streaming path for all tool iterations and only stream the final response. Review the current implementation to determine the best approach.

5. **Refactor `_determine_query_type()` and `_collect_results()`:**
   - These methods currently walk the message list and use `isinstance(msg, AIMessage)` checks.
   - After refactor, messages are dicts from `LLMMessage.get_messages()` with `role` keys.
   - Replace `isinstance(msg, AIMessage)` with `msg["role"] == "assistant"` checks.
   - Replace `msg.content` with `msg["content"]`.
   - Replace `msg.tool_calls` with `msg.get("tool_calls", [])`.

6. **Remove `from langchain_openai import ChatOpenAI`** — confirm no other usages remain in this file.

7. **Run tests:**
   ```bash
   pytest tests/linkedout/intelligence/ -v
   ```

## Files Modified

| File | Change |
|------|--------|
| `src/linkedout/intelligence/agents/search_agent.py` | Full refactor to use LLMClient |

## Implementation Notes

- The `_TOOL_DEFINITIONS` list stays as-is — it's already in the OpenAI tool format that `bind_tools` expects.
- `LLMMessage` already has `add_assistant_message(content, tool_calls=None)` and `add_tool_message(tool_call_id, content)` — these map directly to the tool loop pattern.
- `LLMMessage.to_langchain_messages()` handles conversion back to LangChain types internally — SearchAgent doesn't need to know about this.
- The `ConversationState` tracking may need adjustment since we're changing from LangChain message objects to dicts.

## Completion Criteria

- [ ] No `from langchain_openai import ChatOpenAI` in search_agent.py
- [ ] No `from langchain_core.messages import ...` in search_agent.py
- [ ] `_create_llm_client()` returns `LangChainLLMClient` via `LLMFactory`
- [ ] Tool loop uses `LLMMessage` + `call_llm_with_tools()` + `LLMToolResponse`
- [ ] `_determine_query_type()` and `_collect_results()` work with dict messages
- [ ] `pytest tests/linkedout/intelligence/ -v` passes
- [ ] Langfuse traces appear for SearchAgent calls (manual verification)
