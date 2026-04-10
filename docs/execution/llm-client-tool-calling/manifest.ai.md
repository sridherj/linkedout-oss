# Execution Plan — LLM Client Tool-Calling Support

**Goal:** system-ops
**Source plan:** `docs/plan/llm_client_tool_calling_support.md`
**Created:** 2026-04-01
**Estimated total effort:** ~2-3 sessions (~5-7h) across 4 sub-phases

## Sub-Phases

| # | Name | Plan Section | Est. Effort | Depends On |
|---|------|-------------|-------------|------------|
| SP-1 | Foundation Types | Changes 1, 2, 6 | 0.5 session (~1h) | — |
| SP-2 | call_llm_with_tools | Change 3 | 1 session (~2h) | SP-1 |
| SP-3a | SearchAgent Refactor | Change 4 | 1 session (~2h) | SP-2 |
| SP-3b | WhyThisPersonExplainer Refactor | Change 5 | 0.5 session (~1h) | SP-2 |

## Execution Flow (DAG)

```
SP-1 (Foundation: LLMToolResponse + SystemUser + Exports)
  ↓
SP-2 (call_llm_with_tools abstract + LangChain impl)
  ↓
  ├── SP-3a (SearchAgent refactor)
  └── SP-3b (WhyThisPersonExplainer refactor)
```

## Parallelization Rules

- **SP-1** is sequential (must run first)
- **SP-2** depends on SP-1 (sequential)
- **SP-3a, SP-3b** can run in parallel after SP-2 completes

## Key Artifacts

- **SP-1 output:** `LLMToolResponse` in `llm_schemas.py`, `SystemUser` in `llm_client_user.py`, updated `__init__.py` exports, unit tests for both new types.
- **SP-2 output:** Abstract `call_llm_with_tools()` on `LLMClient`, concrete implementation on `LangChainLLMClient` (bind_tools + invoke + metrics + LLMToolResponse return), unit tests.
- **SP-3a output:** `SearchAgent` rewritten to use `LangChainLLMClient` via `LLMFactory` + `SystemUser`, `run()`/`run_streaming()` use `LLMMessage` + `call_llm_with_tools()`, no direct `ChatOpenAI` import.
- **SP-3b output:** `WhyThisPersonExplainer` rewritten to use `LangChainLLMClient` via `LLMFactory` + `SystemUser`, `explain()` uses `LLMMessage` + `call_llm()`, no direct `ChatOpenAI` import.

## Design Review Flags

| Sub-phase | Flag | Resolution |
|-----------|------|------------|
| SP-2 | `bind_tools` per call vs cached | Per call — cheap operation, no need to cache (plan decision) |
| SP-3a | Tool loop ownership | Stays in SearchAgent — domain logic, not client concern (plan decision) |
| SP-3a | Message type migration | Walk `LLMMessage.get_messages()` dicts instead of `isinstance(msg, AIMessage)` |

## Key Risks

| Risk | Mitigation |
|------|------------|
| SearchAgent tool loop is complex with streaming | SP-3a is largest sub-phase; focus on `run()` first, then `run_streaming()` |
| LangChain `bind_tools` API may differ across versions | Check current pinned version; test with actual tool definitions |
| `_determine_query_type` and `_collect_results` use `isinstance(msg, AIMessage)` | Must rewrite to use dict-based message inspection from `LLMMessage.get_messages()` |
