# Phase D.1: SearchTurn Table (MVCS Stack) + Session Entity Cleanup

**Effort:** ~1 hour
**Dependencies:** Phase C complete
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Create the `search_turn` entity and full MVCS stack. Each search turn writes a new row instead of overwriting `conversation_state` on the session. Also clean up the session entity by dropping obsolete columns.

## What to Do

### 1. Create SearchTurn MVCS stack

Use the `crud-orchestrator-agent` (`.claude/agents/crud-orchestrator-agent.md`) to create:

**Entity:** `./src/linkedout/search_session/entities/search_turn_entity.py`

```python
# search_turn table
# id: prefixed PK ("sturn_xxx")
# session_id: FK → search_session (required)
# turn_number: int, 1-indexed (required)
# user_query: text (required)
# transcript: JSONB — full messages including tool calls/results for this turn
# results: JSONB — the result set produced this turn
# summary: text, nullable — LLM-generated summary, cached after first generation
# created_at: timestamp
```

The entity lives in the existing `search_session` module — no new module needed.

**Repository:** `./src/linkedout/search_session/repositories/search_turn_repository.py`

**Service:** `./src/linkedout/search_session/services/search_turn_service.py`

**Schemas:** 
- `./src/linkedout/search_session/schemas/search_turn_schema.py`
- `./src/linkedout/search_session/schemas/search_turn_api_schema.py`

### 2. Clean up SearchSession entity

**File:** `./src/linkedout/search_session/entities/search_session_entity.py`

**Drop columns:**
- `conversation_state`
- `excluded_ids`
- `accumulated_filters`
- `result_snapshot`
- `status` (no active/archived distinction)

**Keep:**
- `turn_count`
- `initial_query`
- `last_active_at`
- All standard BaseEntity fields

Also update the session schemas to remove references to dropped columns.

### 3. Create Alembic migration

```bash
cd .
alembic revision --autogenerate -m "add search_turn table, drop obsolete session columns"
```

Review the generated migration to ensure it:
- Creates the `search_turn` table with correct columns and FK
- Drops the obsolete columns from `search_session`

### 4. Run compliance check

After CRUD creation, run `crud-compliance-checker-agent` to audit the implementation.

### 5. Add controller endpoint for turn listing

Add a list endpoint for turns by session:
`GET /tenants/{tenant_id}/bus/{bu_id}/search-sessions/{session_id}/turns`

Returns turns ordered by `turn_number` ASC. This is the API the frontend (Phase G.1) will use for session resume.

## Verification

```bash
# Unit tests
pytest tests/unit/search_session/ -v

# Migration check
alembic upgrade head
alembic downgrade -1
alembic upgrade head

# Precommit
precommit-tests
```

## Key Design Notes

- `search_turn.transcript` stores the full LLM messages array for that turn (including tool calls and results). This is the raw data.
- `search_turn.results` stores the structured result set (profiles found, scores, etc.). This is what the frontend renders.
- `search_turn.summary` is lazily populated by ConversationManager (Phase D.2) when history exceeds N turns. Once written, it's never regenerated.
