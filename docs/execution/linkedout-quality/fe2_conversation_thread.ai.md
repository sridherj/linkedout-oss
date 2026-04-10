# FE2: Conversation Thread & Follow-Up UI

## Context
Backend conversational tools are complete (SP6a). The `ConversationTurnResponse` contract returns conversation history, result summary chips, suggested actions, and exclusion state. This sub-phase builds the conversation UI that replaces the static search results page during an active multi-turn session.

## Important: File Resolution
- **Frontend code lives at:** `<linkedout-fe>`
- **Backend code and specs live at:** `.` (also accessible via `.`)
- If a referenced file is not found at one location, check `.`, `.`, or `<prior-project>`
- **Leverage the `/ui-ux-pro-max` skill** for all UI implementation work

## Design Reference
- **HTML mockup:** `<linkedout-fe>/docs/design/conversation-history-followup.html`
- **Design system:** `<linkedout-fe>/docs/design/linkedout-design-system.md`

## Backend Contracts
- **ConversationTurnResponse:** `./src/linkedout/intelligence/contracts.py` — includes `results`, `conversation_history`, `result_summary_chips`, `suggested_actions`, `exclusion_state`
- **ResultSummaryChip:** `{label, count, action_type}` — e.g., "−9 FAANG"
- **SuggestedAction:** `{label, action_type, payload}` — interaction hint chips
- **ExclusionState:** `{excluded_ids, excluded_labels}` — for excluded profiles banner
- **Intelligence spec:** `./docs/specs/linkedout_intelligence.collab.md`
- **Sessions spec:** `./docs/specs/search_sessions.collab.md`

## Frontend Patterns (match these)
- **API client:** `<linkedout-fe>/src/lib/api-client.ts` — `apiFetch<T>(path, options)` with `NEXT_PUBLIC_API_URL` base
- **Streaming search:** `<linkedout-fe>/src/hooks/useStreamingSearch.ts` — SSE via `POST /api/search/stream`, buffers results in `requestAnimationFrame`, uses TanStack Query cache
- **Types:** `<linkedout-fe>/src/types/search.ts` — `ProfileResult` (needs extending for `highlighted_attributes`), `SearchEvent` with types: thinking, result, explanations, done, error
- **UI primitives:** `<linkedout-fe>/src/components/ui/` — button, badge, input, card
- **Styling:** Tailwind with design system tokens (berry-accent, pastel-lavender, pastel-sage, etc.)
- **Components are "use client"** with Next.js App Router

## Existing Frontend Files to Modify/Extend
- `<linkedout-fe>/src/components/search/SearchPageContent.tsx` — major rework: currently renders hero → thinking → results in sequence. Add conversation thread between thinking/search and results. Currently uses `useStreamingSearch()` for data, facet filtering client-side, pagination, batch enrichment panel
- `<linkedout-fe>/src/components/search/SearchBar.tsx` — currently a simple search input with ⌘K shortcut. Transforms to follow-up input bar during active multi-turn session
- `<linkedout-fe>/src/components/search/ThinkingState.tsx` — existing thinking indicator, reuse for turn processing
- `<linkedout-fe>/src/components/search/ResultsList.tsx` — add results header with count + current sort
- `<linkedout-fe>/src/hooks/useStreamingSearch.ts` — needs extension for multi-turn: accept session_id, handle ConversationTurnResponse events

## Activities

### FE2.1 Conversation Thread Component
- New component: `ConversationThread.tsx` in `<linkedout-fe>/src/components/search/`
- Renders above results list
- User bubbles (right-aligned) + system bubbles (left-aligned) with inline result summary chips
- System bubbles include removal chips ("−9 FAANG") and undo indicators
- Turn dividers with "Turn N" labels between conversation segments

### FE2.2 Follow-Up Input Bar
- When session has ≥1 turn, replace the search bar with a follow-up input bar
- Smaller, chat-style input with send button
- Positioned below conversation thread, above results

### FE2.3 Interaction Hint Chips
- Render `suggested_actions` from `ConversationTurnResponse` as clickable chips below the follow-up bar
- Clicking a chip populates the follow-up input and optionally auto-submits
- Examples: "Exclude FAANG", "Sort by tenure", "Show only ML engineers"

### FE2.4 Excluded Profiles Banner
- Banner above results showing excluded count + labels from `exclusion_state`
- "Undo" button to restore excluded profiles
- Example: "9 profiles excluded (FAANG) · Undo"

### FE2.5 Results Header
- Count + current sort indicator: "13 results · sorted by promo recency"
- Updates reactively as filters/sorts are applied via conversation

### FE2.6 Wire Conversation State
- Integrate conversation history from `ConversationTurnResponse` into UI state
- Each new turn appends to thread and updates results below
- Handle loading/thinking state during LLM processing (existing `ThinkingState.tsx` at `<linkedout-fe>/src/components/search/ThinkingState.tsx` may be reusable)

## Verification
- [ ] Conversation thread renders with multi-turn history
- [ ] Follow-up bar appears after first search turn
- [ ] Hint chips render and populate input on click
- [ ] Excluded banner shows with undo functionality
- [ ] Results header updates with count and sort
- [ ] Design matches HTML mockup at `<linkedout-fe>/docs/design/conversation-history-followup.html`
- [ ] Follows design system at `<linkedout-fe>/docs/design/linkedout-design-system.md`
