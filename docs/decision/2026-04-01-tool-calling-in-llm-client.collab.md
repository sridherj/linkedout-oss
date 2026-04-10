# Decision: Tool-calling support lives in LLMClient abstraction, not in consumers

**Date:** 2026-04-01
**Status:** Accepted
**Context:** LLM client abstraction (LangChainLLMClient) and intelligence module (SearchAgent, WhyThisPersonExplainer)

## Question
Should tool-calling (bind_tools + invoke) be handled by the LLM client abstraction or remain as direct ChatOpenAI usage in each consumer?

## Key Findings
- SearchAgent and WhyThisPersonExplainer both imported ChatOpenAI directly, bypassing the shared LLM client
- This bypass meant no Langfuse tracing for the app's most critical LLM calls (search)
- LLMMessage already supported tool message types (add_assistant_message with tool_calls, add_tool_message), so the message layer was ready
- bind_tools is cheap per-call, no caching needed

## Decision
Add `call_llm_with_tools()` to the LLMClient abstract interface and implement in LangChainLLMClient. Migrate all consumers to use the abstraction. Specific sub-decisions:

1. **Tool loop stays in SearchAgent** -- iterating over tool calls and re-invoking is domain logic (decides when to stop, how to handle results), not a client concern
2. **LLMToolResponse** instead of returning raw AIMessage -- prevents LangChain type leakage through the abstraction boundary
3. **SystemUser** for non-BaseAgent callers -- explicit lightweight implementation of LLMClientUser, avoids making the user parameter optional
4. **bind_tools called per-call** -- simple, no stale state risk, negligible cost

## Implications
- All LLM calls now flow through the abstraction, guaranteeing Langfuse tracing
- No ChatOpenAI imports remain in the intelligence module
- Future tool-calling consumers get tracing for free
- Manual verification still needed: start local server, hit search endpoint, confirm Langfuse traces appear

## References
- Plan: `docs/plan/llm_client_tool_calling_support.md`
- Execution manifest: `docs/execution/llm-client-tool-calling/manifest.ai.md`
- Key files: `src/utilities/llm_manager/llm_client.py`, `src/utilities/llm_manager/llm_schemas.py`
