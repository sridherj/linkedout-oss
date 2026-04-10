# Phase D.2: ConversationManager (Generic Infrastructure)

**Effort:** ~1 hour
**Dependencies:** Phase D.1 complete (needs SearchTurn entity)
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Create a generic `ConversationManager` utility in `llm_manager/` that builds conversation history from turn rows — recent N turns verbatim, older turns summarized. Caller provides the summarization prompt. `LLMClient` stays untouched.

## What to Do

### 1. Read the LLMClient spec

**Read:** `./docs/specs/llm_client.collab.md`

Understand the current `LLMClient` contract so `ConversationManager` complements (not modifies) it.

### 2. Read PromptManager usage

**Read:** `./docs/specs/prompt_management.collab.md`

ConversationManager will load its summarization prompt via PromptManager.

### 3. Create ConversationManager

**NEW file:** `./src/utilities/llm_manager/conversation_manager.py`

```python
class ConversationManager:
    def __init__(
        self,
        summarization_prompt: str,  # caller provides — domain-specific
        model: str = "gpt-4.1-mini",  # cheap model for summarization
        recent_turns: int = 4,  # how many turns to keep verbatim
    ):
        ...

    def build_history(
        self, turns: list[dict],  # turn rows from DB (ordered by turn_number)
    ) -> list[dict]:  # messages ready to inject into LLMMessage format
        """Recent N turns verbatim, older turns summarized."""
        # If len(turns) <= self.recent_turns:
        #     return all turns verbatim as messages
        # Else:
        #     older = turns[:-self.recent_turns]
        #     recent = turns[-self.recent_turns:]
        #     For older turns, check if turn.summary exists (cached)
        #     If not, generate summary using self.model + self.summarization_prompt
        #     Return: [summary message] + [recent turns as messages]
        ...
```

**Key behaviors:**
- If conversation has ≤ `recent_turns` turns, return all verbatim — no summarization
- For older turns, check `turn.summary` field first (cached). If present, use it. If not, generate via LLM and return it (caller is responsible for caching back to DB)
- Summary generation uses the cheap model (gpt-4.1-mini) via `LLMClient`
- Returns a list of dicts in the format expected by the SearchAgent's message construction

### 4. Create summarization prompt

**NEW file:** `./prompts/intelligence/summarize_turns.md`

```markdown
Summarize this search conversation concisely. Include:
- What the user was looking for
- Key results found (names, companies)
- Any filters/preferences expressed
Keep the summary under 500 tokens.
```

Loaded via PromptManager with key `intelligence/summarize_turns`.

### 5. Add config

**File:** `./src/shared/config/config.py`

Add:
```python
SUMMARIZE_BEYOND_N_TURNS: int = 4
```

### 6. Create unit tests

**NEW file:** `./tests/unit/utilities/test_conversation_manager.py`

Test cases:
- `test_few_turns_no_summarization` — ≤4 turns returned verbatim
- `test_many_turns_summarizes_older` — >4 turns, older get summarized
- `test_cached_summary_used` — if turn.summary exists, no LLM call made
- `test_summary_generated_when_missing` — if turn.summary is None, LLM called

## Verification

```bash
# Unit tests
pytest tests/unit/utilities/test_conversation_manager.py -v

# Precommit
precommit-tests
```

## Context Construction Per Turn

After this phase, the SearchAgent will construct context like:
```
[system prompt]
+ [cached summary of turns 1..K]     ← from search_turn.summary or generated + cached
+ [recent N turns verbatim]           ← from search_turn.transcript
+ [current user message]
```

This replaces the current `_inject_conversation_history()` method (removed in D.3).
