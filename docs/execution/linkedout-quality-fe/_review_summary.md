# Review Summary: LinkedOut Quality Frontend

## Open Questions — RESOLVED

### Q1: SSE event format for conversation turns — RESOLVED
**Finding:** The backend SSE stream sends: `thinking` → `session` → `result` (per profile) → `explanations` → `done`. The `ConversationTurnResponse` (which has `result_summary_chips`, `suggested_actions`, `exclusion_state`, `result_metadata`, `facets`) is returned by `search_agent.run_turn()` but is **NOT wired into SSE yet**. The controller at `./src/linkedout/intelligence/controllers/search_controller.py` only uses the basic `agent.run()` flow.

**Resolution:** SP3 (conversation thread) needs a **backend change**: add `ConversationTurnResponse` fields to the SSE stream. Options:
- (a) Add a new `conversation_state` SSE event before `done` containing `result_summary_chips`, `suggested_actions`, `exclusion_state`, `result_metadata`
- (b) Bundle them into the `done` event payload

Recommendation: Option (a) — separate event keeps concerns clean and allows the frontend to render conversation state before the final done signal.

**Also note:** The `explanations` event already sends structured `ProfileExplanation` objects (`{explanation: str, highlighted_attributes: [{text, color_tier}]}`) via `.model_dump()` — the frontend `useStreamingSearch.ts` currently only reads the string value (`explanations[r.connection_id]`). SP1 must update this to read the full structured object.

### Q2: SearchPageContent shared modification (SP2a + SP2b) — RESOLVED
**Resolution:** Sequence SP2a before SP2b. Eliminates merge risk at zero cost.

Updated DAG:
```
SP1 (Result Cards) → SP2a (Session Switcher) → SP2b (Profile Slide-Over) → SP3 (Conversation Thread)
```
All sequential. SP2b doesn't block SP3, but running sequentially is safer.

### Q3: Session API response shape — RESOLVED
**Finding:** The backend uses `CRUDRouterFactory` with `PaginateResponseSchema`. The list endpoint returns:
```json
{
  "search_sessions": [...],
  "total": 5,
  "limit": 20,
  "offset": 0,
  "page_count": 1
}
```
The `/latest` custom endpoint returns: `{"search_session": {...}}` (single object, HTTP 404 if none).

**Resolution:** The frontend `useSession` hook must use the paginated wrapper shape for the list. This matches the existing `useSearchHistory.ts` pattern exactly. For `/latest`, unwrap the single object and handle 404 gracefully.

Endpoint paths (all require `X-App-User-Id` header):
- `GET /tenants/{tid}/bus/{bid}/search-sessions` — paginated list
- `GET /tenants/{tid}/bus/{bid}/search-sessions/latest` — latest active (404 if none)
- `GET /tenants/{tid}/bus/{bid}/search-sessions/{id}` — single by ID
- `POST /tenants/{tid}/bus/{bid}/search-sessions` — create new
- `PATCH /tenants/{tid}/bus/{bid}/search-sessions/{id}` — update
- `PATCH /tenants/{tid}/bus/{bid}/search-sessions/{id}/turn` — save turn data

**Note:** The route prefix is `/search-sessions` (hyphenated), NOT `/sessions`.

### Q4: Profile detail endpoint path — RESOLVED
**Finding:** Confirmed at `./src/linkedout/intelligence/controllers/search_controller.py:208`:
```
GET /tenants/{tenant_id}/bus/{bu_id}/search/profile/{connection_id}
```
- Requires `X-App-User-Id` header
- Optional `?query=` param for skill relevance highlighting
- Returns `ProfileDetailResponse` directly (NOT wrapped in `{"profile": ...}`)

## Review Notes by Sub-Phase

### SP1: Result Cards + Highlight Chips
- **Important:** The `explanations` SSE event already sends structured objects (`{explanation: str, highlighted_attributes: [{text, color_tier}]}`), not plain strings. The frontend `useStreamingSearch.ts` line 173 currently reads `explanations[r.connection_id]` as a string — must update to read `.explanation` and `.highlighted_attributes` from the structured object.
- Backward compat: handle both string (old) and object (new) formats with a type guard.
- Card `onClick` + "View profile" button stopPropagation pattern is correct.

### SP2a: Session Switcher & Resume
- Route prefix is `/search-sessions` (hyphenated), not `/sessions`.
- The `result_snapshot` from backend is `[{crawled_profile_id, connection_id}]` — NOT full `ProfileResult`. Session resume needs to re-fetch or store more data.
- Session switcher click-outside-to-close: use `useRef` + `useEffect` with `mousedown`.
- SSE stream already sends `{"type": "session", "payload": {"session_id": "..."}}` — frontend can capture this for session tracking.

### SP2b: Profile Slide-Over Panel
- Responsive widths 1400px/1800px need Tailwind arbitrary breakpoints: `min-[1400px]:` and `min-[1800px]:`.
- Ask tab footer input must persist across tab switches (render in parent, not in tab component).
- Endpoint returns `ProfileDetailResponse` directly (no wrapper).

### SP3: Conversation Thread & Follow-Up
- **REQUIRES BACKEND CHANGE:** Wire `ConversationTurnResponse` fields into SSE stream. See Q1 resolution above.
- Thread auto-scroll: `scrollIntoView({ behavior: "smooth" })`.
- Hint chips `onSelect` → populate follow-up input needs ref or state bridge between `HintChips` and `FollowUpBar`.
