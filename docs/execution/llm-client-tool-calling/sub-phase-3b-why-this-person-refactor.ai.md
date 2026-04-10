# Sub-Phase 3b: WhyThisPersonExplainer Refactor — Use LLMClient Instead of Raw ChatOpenAI

**Goal:** system-ops
**Depends on:** SP-2 (LangChainLLMClient with call_llm must exist; SystemUser from SP-1)
**Estimated effort:** 0.5 session (~1h)
**Source plan section:** Change 5

---

## Objective

Refactor `WhyThisPersonExplainer` to use `LangChainLLMClient` (via `LLMFactory`) instead of constructing `ChatOpenAI` directly. This is simpler than SearchAgent — no tool calling, just a plain `call_llm()` call.

## Context

- `WhyThisPersonExplainer` is at `src/linkedout/intelligence/explainer/why_this_person.py`.
- It currently imports `ChatOpenAI` from `langchain_openai` and constructs it directly.
- It has a simple pattern: build a prompt, call the LLM, parse the text response. No tool calling.
- After refactor, it uses `LLMMessage` + `call_llm()` via `LangChainLLMClient`.
- `SystemUser("why-this-person-explainer")` provides the `LLMClientUser` identity.

## Tasks

1. **Replace imports:**
   - Remove: `from langchain_openai import ChatOpenAI`
   - Add: `from utilities.llm_manager import LLMFactory, LLMMessage, SystemUser`
   - Add: `from utilities.llm_manager.llm_schemas import LLMConfig, LLMProvider`

2. **Replace `_create_llm()` with `_create_llm_client()`:**
   - Current: returns `ChatOpenAI` instance
   - New: returns `LangChainLLMClient` via `LLMFactory.create_client(SystemUser("why-this-person-explainer"), config)`
   - Construct `LLMConfig` from existing settings (same model/key as current `ChatOpenAI` params).

3. **Refactor `explain()` method (or equivalent entry point):**
   - Replace raw LangChain message construction with `LLMMessage`:
     - Build `LLMMessage().add_user_message(prompt_text)` (the explainer likely uses a single user message with the formatted prompt)
   - Replace `llm.invoke(messages)` with `client.call_llm(msg)`
   - The response is already a `str` from `call_llm()` — no change needed for `_parse_explanations()`.

4. **Remove `from langchain_openai import ChatOpenAI`** — confirm no other usages remain.

5. **Run tests:**
   ```bash
   pytest tests/linkedout/intelligence/explainer/ -v
   pytest tests/linkedout/intelligence/ -v
   ```

## Files Modified

| File | Change |
|------|--------|
| `src/linkedout/intelligence/explainer/why_this_person.py` | Refactor to use LLMClient |

## Implementation Notes

- This is significantly simpler than SP-3a because there's no tool loop — just a straightforward prompt → response flow.
- The `_PROMPT_TEMPLATE` and `_format_result` / `_parse_explanations` helper functions are unchanged.
- The LLM client instance could be created once per `explain()` call or cached on the class — follow whatever pattern the current `_create_llm()` uses.

## Completion Criteria

- [ ] No `from langchain_openai import ChatOpenAI` in why_this_person.py
- [ ] `_create_llm_client()` returns `LangChainLLMClient` via `LLMFactory`
- [ ] `explain()` uses `LLMMessage` + `call_llm()`
- [ ] `_parse_explanations()` still works (response is still a string)
- [ ] `pytest tests/linkedout/intelligence/explainer/ -v` passes
- [ ] `pytest tests/linkedout/intelligence/ -v` passes (no regressions)
- [ ] Langfuse traces appear for explainer calls (manual verification)
