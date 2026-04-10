# Sub-phase 5: Session Persistence — Search Sessions & History

## Prerequisites
- **SP4 complete** (Phase 1 complete -- search quality must be good before building conversation on top)

## Outcome
Search results and conversation history persist server-side. Users can close the browser, return, and see previous results. Search page loads the most recent active session by default.

## Estimated Effort
4-5 sessions

## Verification Criteria
- [ ] Create search, close browser, reopen -- results still there with conversation history
- [ ] Session load <500ms for 100 results + 20-turn history
- [ ] New search creates new session, archives previous
- [ ] Session history navigable (list of past sessions with query summaries)
- [ ] SearchSession is standalone entity (no FK to SearchHistory, no backward compat)
- [ ] New spec `search_sessions.collab.md` created and registered

---

## Activities

### 5.1 Data Model — SearchSession Entity
- Extends `BaseEntity` + `TenantBuMixin`
- Fields:
  - `app_user_id` (FK to app_user)
  - `initial_query` (text)
  - `conversation_state` (JSONB -- full LLM message history, structured summary)
  - `result_snapshot` (JSONB -- profile IDs + ranking + metadata per turn)
  - `accumulated_filters` (JSONB -- active filters/exclusions)
  - `excluded_ids` (JSONB -- list of excluded profile IDs)
  - `turn_count` (integer)
  - `status` (enum: active, archived)
  - `last_active_at` (datetime)
- **Spike reference:** Multi-turn spike created experimental `ConversationState` with `structured_summary` in `contracts.py` and `run_turn()` in `search_agent.py`. These validate the approach but are NOT production code -- design production versions fresh.
- **MUST use `.claude/agents/crud-orchestrator-agent`** to generate the full MVCS stack. This agent delegates to specialized sub-agents (`entity-creation-agent`, `schema-creation-agent`, `repository-agent`, `service-agent`, `controller-agent` + their test agents). Invoke it for SearchSession first, then SearchTag. Do NOT hand-write CRUD layers manually.

### 5.2 Data Model — SearchTag Entity
- Extends `BaseEntity` + `TenantBuMixin`
- Fields:
  - `app_user_id` (FK)
  - `session_id` (FK to SearchSession -- provenance, Decision #12)
  - `crawled_profile_id` (FK)
  - `tag_name` (text)
- Tags are global per user with session-aware provenance
- Indexes: `(app_user_id, tag_name)`, `(app_user_id, crawled_profile_id)`, `(session_id)`

### 5.3 Alembic Migration
- Create both tables with indexes
- `app_user_id + last_active_at` index on SearchSession for fast "load most recent active"
- SearchSession is standalone -- no FK to SearchHistory, no backward compat

### 5.4 SearchSession CRUD Stack
- **Use `.claude/agents/crud-orchestrator-agent`** for both SearchSession and SearchTag. This generates: entity, schemas (enums, core, API), repository, service, controller, and wiring tests for each layer.
- After CRUD generation, **add custom methods** to the generated service:
  - `get_latest_active(app_user_id)` -- load most recent active session
  - `archive_session(session_id)` -- mark as archived
  - `save_turn(session_id, turn_data)` -- persist updated conversation state + result snapshot
- After CRUD generation, **add custom endpoints** to the generated controller (use `.claude/agents/custom-controller-agent` if needed):
  - `GET /sessions/latest` -- most recent active session
  - `POST /sessions` -- create new (archives current active)
  - `PATCH /sessions/{id}` -- save turn state
- Standard CRUD endpoints (`GET /sessions`, `GET /sessions/{id}`) come from the generated controller via `CRUDRouterFactory`

### 5.5 Modify Search Flow
- On new search: create SearchSession, persist initial results + conversation state
- On follow-up turn: load session, inject conversation history as context, execute turn, save updated state
- On page load: `GET /sessions/latest` returns most recent active session with results and history (no re-execution)
- On explicit "New Search": archive current session, create new one

### 5.6 Conversation History Replay
- Design production `ConversationConfig` with `context_strategy: ContextStrategy` enum:
  - `FULL_HISTORY` -- send all turns verbatim
  - `SLIDING_WINDOW` -- structured summary of older turns + recent N verbatim (default)
  - `SUMMARY_ONLY` -- only structured summary
- Default: `SLIDING_WINDOW` with `summary_window_size=2` (spike-validated)
- **Plan Review Amendment A1:** Rename spike's `ReplayMode` -> `ContextStrategy`. Rename field `replay_mode` -> `context_strategy`.
- Do NOT re-execute the original query on resume -- load results from session snapshot
- **Spike reference:** `spike_multiturn_conversation_results.ai.md` -- sliding window with summary_window_size=2 outperforms other modes. Structured summary beats raw history replay.

### 5.7 Extend Langfuse Tracing
- Group traces by `session_id` (now a real session ID from the database, replacing the generated UUID from SP1)
- Each turn within a session is a separate trace, linked by session_id
- Session-level view in Langfuse: all traces for a session, ordered by turn number

### 5.8 Frontend
- **Design reference:** `<linkedout-fe>/docs/design/session-history-new-search.html`
- Search bar row: search input + session switcher dropdown + "New Search" button
- Session dropdown: scrollable list with query text, status tag (Active/Archived), timestamp (relative), result count, turn count, resume button
- Active session label: dot indicator + "Active session · Turn N"
- Search page loads existing session results by default (not empty search box)
- API contract:
  - `GET /sessions` -> `[{id, initial_query, status, last_active_at, result_count, turn_count}]`
  - `GET /sessions/{id}` -> full session state
  - `GET /sessions/latest` -> most recent active
  - `POST /sessions` -> creates new, archives current

### 5.9 Create Spec: `search_sessions.collab.md`
- `/taskos-update-spec` to create new spec covering:
  - SearchSession entity: fields, JSONB structure, lifecycle (active/archived), session resume with sliding-window context replay
  - SearchTag entity: fields, global per user, session-aware provenance
  - Session CRUD contracts
  - Context engineering contract: what the LLM sees per turn
  - Session API endpoints
  - Performance target: session load <500ms
  - Decisions: standalone entity, TenantBuMixin, JSONB for conversation state
- Register in `docs/specs/_registry.md`

---

## Design Review Notes

| ID | Issue | Resolution |
|----|-------|------------|
| A1 | `ReplayMode` -> `ContextStrategy` with FULL_HISTORY, SLIDING_WINDOW, SUMMARY_ONLY | Plan Review amendment. Rename field to `context_strategy` |
| Architecture | JSONB for conversation_state could grow large (50+ turns) | Start with JSONB. Structured summary compresses older turns. Refactor to normalized table if >1MB/session |
| Naming | SearchSession vs SearchConversation | "Session" aligns with requirements language and `session_id` in tracing |
| No compat | SearchHistory ignored | Standalone entity. No FK, no migration. Drop SearchHistory later |
| Security | Session data is tenant-scoped | TenantBuMixin + app_user_id FK. Verify endpoints check both |
| Error path | Session load fails | Fallback to empty search box (new session). Never show another user's session |

## Key Files to Read First
- `src/linkedout/shared/infra/db_session_manager.py` -- DB session management
- `src/linkedout/intelligence/contracts.py` -- spike contracts to inform (not extend)
- `src/linkedout/intelligence/agents/search_agent.py` -- search flow to modify
- `docs/specs/linkedout_crud.collab.md` -- MVCS patterns for new entities
- `.taskos/spike_multiturn_conversation_results.ai.md` -- sliding window validation
- `.taskos/exploration/playbook_conversational_search.ai.md` -- session persistence playbook
- `<linkedout-fe>/docs/design/session-history-new-search.html` -- UI design
