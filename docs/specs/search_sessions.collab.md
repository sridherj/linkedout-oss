---
feature: search-sessions
module: backend/src/linkedout/search_session, backend/src/linkedout/search_tag, backend/src/linkedout/intelligence
linked_files:
  - backend/src/linkedout/search_session/
  - backend/src/linkedout/search_session/entities/search_session_entity.py
  - backend/src/linkedout/search_session/entities/search_turn_entity.py
  - backend/src/linkedout/search_session/controllers/search_session_controller.py
  - backend/src/linkedout/search_session/controllers/search_turn_controller.py
  - backend/src/linkedout/search_tag/
  - backend/src/linkedout/search_tag/entities/search_tag_entity.py
  - backend/src/linkedout/intelligence/agents/search_agent.py
  - backend/src/linkedout/intelligence/controllers/search_controller.py
  - backend/src/linkedout/intelligence/controllers/_sse_helpers.py
  - backend/src/linkedout/intelligence/contracts.py
  - backend/src/linkedout/query_history/query_logger.py
version: 1
last_verified: "2026-04-09"
---

# Search Sessions & History

## Intent

Search conversations persist server-side as a series of turns. Users can close the browser, return, and see previous results. The frontend owns the session lifecycle -- the backend has no pivot detection, auto-archiving, or active/archived status. Each search turn writes a new `search_turn` row rather than overwriting state on the session entity.

## Entities

### SearchSession

Scoped entity (`TenantBuMixin` + `BaseEntity`). Lightweight session header -- all conversation content lives in `SearchTurn` rows.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | String (ss_ prefix) | auto | Unique identifier |
| tenant_id, bu_id | String | auto | Tenant/BU scope |
| app_user_id | String, FK app_user.id | yes | Session owner |
| initial_query | Text | yes | First search query |
| turn_count | Integer | yes (default 1) | Number of conversation turns |
| last_active_at | DateTime(tz) | yes | Last activity timestamp |
| is_saved | Boolean | yes (default False) | Whether session was explicitly saved/bookmarked |
| saved_name | Text | no | User-provided name for the saved session |

**Indexes:** `(app_user_id, last_active_at)`, `(app_user_id, is_saved)`

### SearchTurn

Scoped entity (`TenantBuMixin` + `BaseEntity`). Stores a single conversation turn within a session. The PATCH endpoint allows updating `transcript`, `results`, and `summary` (all three are optional on update). The primary use case for updates is lazy `summary` population by `ConversationManager`; `transcript` and `results` updates support fire-and-forget persistence where the initial write may be partial.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | String (sturn_ prefix) | auto | Unique identifier |
| tenant_id, bu_id | String | auto | Tenant/BU scope |
| session_id | String, FK search_session.id | yes | Parent session |
| turn_number | Integer | yes | 1-indexed turn number within session |
| user_query | Text | yes | User's query for this turn |
| transcript | JSONB | no | `{messages: [...]}` -- full LLM messages array including tool calls/results |
| results | JSONB | no | Structured result set (profiles, scores, explanations merged in) |
| summary | Text | no | LLM-generated summary, lazily populated by ConversationManager |

**Indexes:** `(session_id, turn_number)`

**History reconstruction:**
```sql
SELECT * FROM search_turn WHERE session_id = :id ORDER BY turn_number
```

### SearchTag

Scoped entity (`TenantBuMixin` + `BaseEntity`). User-applied tags on profiles with session provenance.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | String (stag_ prefix) | auto | Unique identifier |
| tenant_id, bu_id | String | auto | Tenant/BU scope |
| app_user_id | String, FK app_user.id | yes | Tag creator |
| session_id | String, FK search_session.id | yes | Session provenance |
| crawled_profile_id | String, FK crawled_profile.id | yes | Tagged profile |
| tag_name | Text | yes | Tag label |

**Indexes:** `(app_user_id, tag_name)`, `(app_user_id, crawled_profile_id)`, `(session_id)`

Tags are global per user -- the same tag_name applied in different sessions creates separate records with different session provenance.

## Session Lifecycle

**Frontend-owned.** The backend does not manage session transitions.

1. **New search:** Frontend sends no `session_id` -> backend creates a new `SearchSession` (via `create_or_resume_session()` in `_sse_helpers.py`), streams results, saves a `SearchTurn` row with `turn_number=1`.
2. **Follow-up turn:** Frontend sends existing `session_id` -> backend loads turn history from `search_turn` rows ordered by `turn_number`, injects as context via `ConversationManager.build_history()`, runs the agent, saves a new `SearchTurn` row, increments `turn_count` and updates `last_active_at`.
3. **Page load (resume):** Frontend queries the list endpoint sorted by `last_active_at desc` (limit 1), then fetches turns via the nested listing endpoint.
4. **Explicit "New Search":** Frontend simply omits `session_id` -- a new session is created. The old session is not modified.

There is no `status` column, no active/archived distinction, no auto-archiving, and no pivot detection. All sessions are read-only historical records plus the most recent active one (determined by `last_active_at`).

## Context Engineering

Turn history is reconstructed from `search_turn` rows and passed to `SearchAgent.run_turn()` as `turn_history`. Each turn dict contains: `user_query` (str), `transcript` (messages list from `transcript.messages`), `summary` (str, lazily populated). The `ConversationManager` (in `backend/src/utilities/llm_manager/`) handles context window construction:

- Each prior turn's `transcript.messages` provides the full LLM conversation
- `summary` field (lazily populated) compresses older turns for token efficiency
- The caller (search controller) provides the summarization prompt; `ConversationManager` is generic infrastructure

See [llm_client spec](llm_client.collab.md) for `ConversationManager` details.

## Behaviors

### Turn Persistence (Backend)

After the SSE stream completes, `save_session_state()` in `_sse_helpers.py`:
1. Looks up the existing session by ID
2. Creates a new `SearchTurnEntity` with `turn_number = existing.turn_count + 1`
3. Stores the user query, full LLM transcript (`{messages: [...]}` from `turn_response.turn_transcript`), summary (from `turn_response.message`), and results (merged with explanation data via `merge_results_with_explanations()`)
4. Updates the session's `turn_count` and `last_active_at` via the service update path

This is fire-and-forget -- persistence failure does not break the search response (wrapped in try/except with warning log).

### SSE Conversation Protocol (Backend)

**Session event**: Early in the stream, a `session` SSE event carries the `session_id` (new or existing) so the frontend can track it.

**Thinking events**: Progress messages emitted during tool execution (e.g., "Starting search...", "Generating explanations...").

**Result events**: Individual `result` events carry each `SearchResultItem` as they are produced from `run_turn()`.

**Explanations events**: After results, `explanations` events carry batches of `ProfileExplanation` data (if `explain=True`).

**Conversation state event**: After results and explanations, a `conversation_state` event carries `result_summary_chips`, `suggested_actions`, `result_metadata`, and `facets`.

**Done event**: Final event with `total`, `query_type`, `answer`, and `session_id`.

**Heartbeat**: Every 15 seconds if no events are produced, a `heartbeat` event is emitted to prevent idle timeout.

### Query History (JSONL Legacy)

The `query_history` module (`backend/src/linkedout/query_history/`) provides file-based query logging to `~/linkedout-data/queries/YYYY-MM-DD.jsonl`. This is a legacy mechanism separate from session persistence. Each entry records: timestamp, query_id, session_id, query_text, query_type, result_count, duration_ms, model_used, is_refinement. Thread-safe via `fcntl.flock()` advisory locking. Note: There is no `SearchHistory` database entity in OSS -- this was fully replaced by `SearchSession` + `SearchTurn`.

## API Endpoints

### Standard CRUD (via CRUDRouterFactory)

**SearchSession:** Standard CRUD endpoints at `/tenants/{tenant_id}/bus/{bu_id}/search-sessions/`. Configured via `CRUDRouterConfig` with meta_fields: `sort_by`, `sort_order`, `app_user_id`, `is_saved`.

**SearchTurn:** Standard CRUD endpoints at `/tenants/{tenant_id}/bus/{bu_id}/search-turns/`. Configured with meta_fields: `sort_by`, `sort_order`, `session_id`. List endpoint supports `session_id` query filter for scoping to a session.

### Nested Turn Listing

`GET /tenants/{tenant_id}/bus/{bu_id}/search-turns/by-session/{session_id}` -- Lists all turns for a session ordered by `turn_number ASC`. Supports `limit` (default 100, max 500) and `offset` (default 0) query params. Returns `ListSearchTurnsResponseSchema` with `search_turns`, `total`, `limit`, `offset`, `page_count`.

### Search Endpoint Integration

The existing `POST /tenants/{tenant_id}/bus/{bu_id}/search` SSE endpoint creates/resumes sessions:
- First search (no `session_id`): creates session, streams results, saves turn
- Follow-up (with `session_id`): loads turn history, injects context, streams results, saves turn
- Session ID is passed to Langfuse for trace grouping

### Best Hop Integration

`POST /tenants/{tenant_id}/bus/{bu_id}/best-hop` also creates/resumes sessions and persists turn data using the shared `create_or_resume_session()` and `save_session_state()` helpers.

## Langfuse Tracing

- Session traces use real `SearchSession.id`
- Each turn within a session is a separate Langfuse trace, linked by `session_id`
- The search controller wraps agent execution in `langfuse.start_as_current_observation()` with session_id metadata

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-04-02 | Entity relationship | Standalone SearchSession | FK to SearchHistory | Clean break; SearchHistory is removed in OSS |
| 2026-04-02 | Conversation storage | Normalized `search_turn` table | JSONB in SearchSession | Each turn is immutable; enables per-turn queries and lazy summary |
| 2026-04-02 | Session lifecycle owner | Frontend | Backend (pivot detection) | Simpler backend; frontend has the UX context to decide new vs. continue |
| 2026-04-02 | Tag provenance | session_id FK on SearchTag | No provenance | Enables "what tags were applied in this session" queries |
| 2026-04-02 | Removed status column | No active/archived | status enum | Frontend-owned lifecycle; no backend logic needs the distinction |

## Edge Cases

### Long conversations (20+ turns)
- ConversationManager uses a sliding window + summary strategy. Older turns are summarized (lazily written to `search_turn.summary`), recent turns are passed verbatim. Token usage stays bounded.

### Tag operations across sessions
- Tags have session provenance (session_id FK) but are global per user. Retrieving tags via `get_tagged_profiles` without a session_id returns tags from all sessions. Tags survive regardless of session age.

### Concurrent sessions from same user
- No enforcement of single active session. The frontend controls which session_id to send. If two tabs search simultaneously, each creates its own session. No cross-contamination because each session has its own turn history.

### Stale session_id
- If the frontend sends a `session_id` that doesn't exist, the backend creates a new session (treats it as a new search). This is handled in `create_or_resume_session()` -- the lookup returns None, so the code falls through to session creation.

### Saved sessions
- The `is_saved` flag and `saved_name` field allow users to bookmark sessions. The `(app_user_id, is_saved)` index supports efficient queries for saved sessions. Saving is a simple PATCH update via the CRUD endpoint.

## Not Included

- Tag-based search filtering (future: search within tagged profiles)
- Session sharing between users
- Session export/import
- Conversation branching (fork from mid-conversation)
- Auto-archiving of stale sessions (can add via background job later)
- Backend-driven pivot detection
