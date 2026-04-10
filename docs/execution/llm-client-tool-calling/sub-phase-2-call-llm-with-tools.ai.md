# Sub-Phase 2: call_llm_with_tools — Abstract + LangChain Implementation

**Goal:** system-ops
**Depends on:** SP-1 (LLMToolResponse and SystemUser must exist)
**Estimated effort:** 1 session (~2h)
**Source plan section:** Change 3

---

## Objective

Add an abstract `call_llm_with_tools()` method to `LLMClient` and implement it in `LangChainLLMClient`. The method accepts an `LLMMessage` and a list of tool definitions, calls the LLM with tools bound, and returns an `LLMToolResponse`.

## Context

- `LLMClient` (ABC) is in `src/utilities/llm_manager/llm_client.py` and currently has 3 abstract methods: `call_llm`, `call_llm_structured`, `acall_llm_stream`.
- `LangChainLLMClient` implements all three using LangChain's `invoke`/`astream` with Langfuse callbacks.
- The new method follows the same pattern as `call_llm()`: convert messages → invoke → record metrics → return.
- The key difference: before invoking, call `self._llm.bind_tools(tools)` to get a tools-bound model, then invoke that. Parse `AIMessage.tool_calls` from the response into `LLMToolResponse.tool_calls`.
- `bind_tools` is called per-call (not cached) — this is a deliberate design decision from the plan.

## Tasks

1. **Add import for `LLMToolResponse`** in `src/utilities/llm_manager/llm_client.py`:
   ```python
   from utilities.llm_manager.llm_schemas import LLMConfig, LLMProvider, LLMToolResponse
   ```
   (Add `LLMToolResponse` to the existing import from `llm_schemas`.)

2. **Add abstract method to `LLMClient`:**
   ```python
   @abstractmethod
   def call_llm_with_tools(self, message: LLMMessage, tools: list[dict]) -> LLMToolResponse:
       """Make a synchronous call to the LLM with tool definitions bound."""
       pass
   ```
   Place after `call_llm` and before `call_llm_structured`.

3. **Implement in `LangChainLLMClient`:**
   ```python
   def call_llm_with_tools(self, message: LLMMessage, tools: list[dict]) -> LLMToolResponse:
       lc_messages = message.to_langchain_messages()
       tools_llm = self._llm.bind_tools(tools)

       start_ns = time.perf_counter_ns()
       response = tools_llm.invoke(
           lc_messages,
           config={'callbacks': self._get_callbacks()}
       )
       latency_ms = round((time.perf_counter_ns() - start_ns) / 1_000_000, 2)
       self._record_llm_metrics(response, response.content, latency_ms)

       # Convert LangChain tool_calls to plain dicts
       tool_calls = []
       if hasattr(response, 'tool_calls') and response.tool_calls:
           for tc in response.tool_calls:
               tool_calls.append({
                   "id": tc.get("id", ""),
                   "name": tc.get("name", ""),
                   "args": tc.get("args", {}),
               })

       return LLMToolResponse(
           content=str(response.content),
           tool_calls=tool_calls,
       )
   ```
   Place after `call_llm` implementation and before `call_llm_structured` implementation.

4. **Write tests in `tests/utilities/llm_manager/test_llm_client.py`** (extend existing file):
   - **Test `call_llm_with_tools` calls `bind_tools` + `invoke`:** Mock `self._llm.bind_tools()` to return a mock model, mock that model's `invoke()` to return a fake `AIMessage` with `tool_calls`. Assert `LLMToolResponse` is returned with correct content and tool_calls.
   - **Test `call_llm_with_tools` with no tool calls:** Mock response has empty `tool_calls`. Assert `LLMToolResponse.has_tool_calls` is `False`.
   - **Test `call_llm_with_tools` records metrics:** Assert `_record_llm_metrics` is called with the response.

## Files Modified

| File | Change |
|------|--------|
| `src/utilities/llm_manager/llm_client.py` | Add import, abstract method, implementation |
| `tests/utilities/llm_manager/test_llm_client.py` | Add tests for `call_llm_with_tools` |

## Implementation Notes

- LangChain's `AIMessage.tool_calls` is a `list[ToolCall]` where `ToolCall` is a `TypedDict` with keys `name`, `args`, `id`. The implementation maps these to plain dicts matching the `LLMToolResponse` contract.
- The `bind_tools` method accepts the same OpenAI-format tool definitions that `SearchAgent` already constructs (the `_TOOL_DEFINITIONS` list).
- Error handling: if `invoke` raises, let it propagate (same pattern as `call_llm`). No special handling needed.

## Completion Criteria

- [ ] `LLMClient.call_llm_with_tools` exists as abstract method
- [ ] `LangChainLLMClient.call_llm_with_tools` binds tools and returns `LLMToolResponse`
- [ ] Tool calls from LangChain `AIMessage` are correctly mapped to `LLMToolResponse.tool_calls`
- [ ] Metrics are recorded (same pattern as `call_llm`)
- [ ] `pytest tests/utilities/llm_manager/test_llm_client.py -v` passes
- [ ] `pytest tests/utilities/llm_manager/ -v` passes (no regressions)
