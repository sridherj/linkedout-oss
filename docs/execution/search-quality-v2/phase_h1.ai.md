# Phase H.1: Update search_sessions Spec

**Effort:** 30 min
**Dependencies:** Phase D complete (implementation must be stable before updating spec)
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Major rewrite of the search_sessions spec to reflect the new turn-based model.

## What to Do

### 1. Read current spec

**File:** `./docs/specs/search_sessions.collab.md`

### 2. Use the taskos-update-spec agent

Invoke `/taskos-update-spec` with these changes:

**Remove from spec:**
- `conversation_state` column description and behavior
- `excluded_ids` column
- `accumulated_filters` column
- `result_snapshot` column
- `status` column (active/archived distinction)
- `ContextStrategy` enum references
- Pivot detection behavior
- Auto-archiving behavior (`get_latest_active`)
- `ConversationState`, `ConversationConfig` contract descriptions

**Add to spec:**
- `SearchTurn` entity: `id`, `session_id` (FK), `turn_number`, `user_query`, `transcript` (JSONB), `results` (JSONB), `summary` (text, nullable), `created_at`
- Turn-based conversation model: each turn writes a new row
- History reconstruction: `SELECT * FROM search_turn WHERE session_id = ? ORDER BY turn_number`
- Summary caching: `search_turn.summary` populated lazily by ConversationManager
- Session lifecycle: frontend-owned, no active/archived, no pivot detection
- Session entity simplified: `turn_count`, `initial_query`, `last_active_at` + BaseEntity fields

**Update:**
- API endpoints: add `GET /search-sessions/{id}/turns`
- Data model diagram
- Cross-references to ConversationManager (in llm_client spec, Phase H.3)

## Verification

- Spec accurately reflects the implemented code (Phase D)
- No references to removed concepts
- Cross-references are correct
