# Sub-phase F: Backend Tests

**Effort:** 2-3 sessions
**Dependencies:** C (service), D (controller), E (prompt) — all backend implementation must be complete
**Working directory:** `.`
**Shared context:** `_shared_context.md`
**Agents:** `service-test-agent`, `controller-test-agent`, `integration-test-creator-agent`

---

## Objective

Write unit tests for the service and controller, plus integration tests for the full `/best-hop` endpoint against a real PostgreSQL database.

## What to Do

### 1. Service Unit Tests

**File:** `tests/unit/intelligence/services/test_best_hop_service.py`
**Agent:** `service-test-agent`

Test cases:
- **`test_assemble_context_happy_path`**: Mock DB session with target + 5 mutuals (3 matched, 2 unmatched). Verify context has correct matched/unmatched counts and all SQL data populated.
- **`test_assemble_context_target_not_found`**: Target URL not in DB → raises clear error.
- **`test_assemble_context_no_mutuals_matched`**: All URLs unmatched → context has empty mutuals list, unmatched_count = len(mutual_urls).
- **`test_build_prompt_includes_target`**: Verify prompt includes target name, position, experience.
- **`test_build_prompt_includes_mutuals_with_affinity`**: Verify prompt includes mutual profiles with affinity scores.
- **`test_rank_merges_llm_and_sql_data`**: Mock LLM response returning `{crawled_profile_id, rank, why_this_person}`. Verify result items have SQL-sourced fields (connection_id, full_name, etc.) merged in.
- **`test_rank_limits_to_30`**: If LLM returns >30, only 30 yielded.

### 2. Controller Unit Tests

**File:** `tests/unit/intelligence/controllers/test_best_hop_controller.py`
**Agent:** `controller-test-agent`

Test cases:
- **`test_best_hop_returns_sse_stream`**: Mock service, verify response is `text/event-stream` with correct headers.
- **`test_best_hop_event_sequence`**: Mock service yielding 3 results. Verify SSE events in order: `thinking`, `session`, `thinking` (found N of M), `result` x3, `done`.
- **`test_best_hop_requires_app_user_id`**: Missing `X-App-User-Id` header → 422.
- **`test_best_hop_error_yields_error_event`**: Service raises exception → SSE error event emitted.

### 3. Integration Tests

**File:** `tests/integration/linkedout/intelligence/test_best_hop_integration.py`
**Agent:** `integration-test-creator-agent`

These run against a real PostgreSQL test database.

**Setup:** Seed test data:
- 1 app_user with connections
- 1 target profile (enriched, with experience)
- 5 mutual connections (3 in DB with affinity scores + experience, 2 not in DB)

Test cases:
- **`test_best_hop_happy_path`**: POST `/best-hop` with target + 5 mutual URLs. Verify:
  - SSE stream has `session`, `thinking`, `result` (at least 1), `done` events
  - `done` payload has `matched=3, unmatched=2`
  - Each `result` has `connection_id`, `full_name`, `why_this_person`, `rank`
  - Results are ordered by rank
- **`test_best_hop_all_unmatched`**: POST with URLs not in DB. Verify:
  - No `result` events (or LLM returns empty)
  - `done` has `matched=0, unmatched=N`
- **`test_best_hop_partial_match`**: Mix of known/unknown URLs. Verify correct matched/unmatched counts.
- **`test_best_hop_session_persisted`**: After stream completes, verify SearchSession and SearchTurn rows exist in DB with `initial_query` containing "Best hop".

## Verification

```bash
# Unit tests
pytest tests/unit/intelligence/services/test_best_hop_service.py -v
pytest tests/unit/intelligence/controllers/test_best_hop_controller.py -v

# Integration tests (requires PostgreSQL)
pytest tests/integration/linkedout/intelligence/test_best_hop_integration.py -v

# Full suite
pytest tests/ -k "best_hop" -v
```

## What NOT to Do

- Do not test the LLM's ranking quality — that's manual E2E (plan verification step 4)
- Do not mock the database in integration tests — use real PostgreSQL
- Do not test SSE helper functions separately — they're tested through search controller tests
