# Phase H.3: Update llm_client Spec

**Effort:** 15 min
**Dependencies:** Phase D.2 complete (ConversationManager implemented)
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Add ConversationManager as a companion utility to the llm_client spec.

## What to Do

### 1. Read current spec

**File:** `./docs/specs/llm_client.collab.md`

### 2. Use the taskos-update-spec agent

Invoke `/taskos-update-spec` with these changes:

**Add:**
- `ConversationManager` section as a companion utility in `src/utilities/llm_manager/`
- Note that `LLMClient` itself is unchanged — ConversationManager is a separate class
- API: `ConversationManager(summarization_prompt, model, recent_turns)` + `build_history(turns) -> messages`
- Behavior: recent N turns verbatim, older turns summarized using caller's prompt
- Summary caching: caller responsible for persisting generated summaries back to DB
- Configuration: `SUMMARIZE_BEYOND_N_TURNS` in config

## Verification

- Spec clearly distinguishes LLMClient (unchanged) from ConversationManager (new)
- ConversationManager API matches implementation
