# Sub-phase 3: Conversation Thread & Follow-Up UI

> **Pre-requisite:** Read `./docs/execution/linkedout-quality-fe/_shared_context.md` before starting this sub-phase.

## Objective

Build the multi-turn conversation UI that replaces the static search results flow during an active session. When a session has turns, the page shows: conversation thread (user/system bubbles with inline result summary chips), a follow-up input bar, suggested action hint chips, an excluded-profiles banner, and an updated results header. This transforms LinkedOut from a one-shot search into a conversational interface.

## Dependencies
- **Requires completed:** SP1 (Result Cards), SP2a (Session Switcher) -- session state management, session_id in search requests, activeSessionId
- **Assumed codebase state:** Session hooks exist (`useSession.ts`), `SearchPageContent` manages active session, `useStreamingSearch` accepts `session_id`, `ProfileResult` has `highlighted_attributes`

## Scope
**In scope:**
- Create `ConversationThread.tsx` -- renders above results list
- Create `FollowUpBar.tsx` -- chat-style input replacing search bar during active multi-turn session
- Create `HintChips.tsx` -- suggested action chips from `ConversationTurnResponse.suggested_actions`
- Create `ExcludedBanner.tsx` -- banner showing excluded profiles count with undo
- Update `ResultsList.tsx` header to show count + sort description from `result_metadata`
- Extend `useStreamingSearch.ts` to handle `ConversationTurnResponse` events (conversation_state, result_summary_chips, suggested_actions, exclusion_state)
- Wire conversation state into `SearchPageContent` -- maintain turn history, render thread
- Visually match HTML mockup at `<linkedout-fe>/docs/design/conversation-history-followup.html`

**Out of scope (do NOT do these):**
- Profile slide-over panel (SP2b -- separate)
- Backend changes
- Card styling changes (SP1 done)
- Session CRUD (SP2a done)
- Undo exclusion backend call (wire the UI button, log action for now)

## Files to Create/Modify

| File | Action | Current State |
|------|--------|---------------|
| `<linkedout-fe>/src/types/conversation.ts` | Create | Does not exist |
| `<linkedout-fe>/src/components/search/ConversationThread.tsx` | Create | Does not exist |
| `<linkedout-fe>/src/components/search/FollowUpBar.tsx` | Create | Does not exist |
| `<linkedout-fe>/src/components/search/HintChips.tsx` | Create | Does not exist |
| `<linkedout-fe>/src/components/search/ExcludedBanner.tsx` | Create | Does not exist |
| `<linkedout-fe>/src/components/search/SearchPageContent.tsx` | Modify | Has session state from SP2a |
| `<linkedout-fe>/src/components/search/ResultsList.tsx` | Modify | Static header |
| `<linkedout-fe>/src/hooks/useStreamingSearch.ts` | Modify | No conversation turn handling |

## Detailed Steps

### Step 3.1: Create Conversation Types

Create `<linkedout-fe>/src/types/conversation.ts`:

```typescript
export interface ResultSummaryChip {
  text: string;   // e.g. "13 results", "-9 FAANG"
  type: "count" | "filter" | "sort" | "removal";
}

export interface SuggestedAction {
  type: "narrow" | "rank" | "exclude" | "broaden" | "ask";
  label: string;  // e.g. "Only SF / NYC", "Rank by affinity"
}

export interface ExclusionState {
  excluded_count: number;
  excluded_description: string;  // e.g. "9 FAANG profiles removed"
  undoable: boolean;
}

export interface ResultMetadata {
  count: number;
  sort_description: string;  // e.g. "sorted by promo recency"
}

export interface ConversationTurn {
  userMessage: string;
  systemMessage: string;
  resultSummaryChips: ResultSummaryChip[];
  turnNumber: number;
}
```

### Step 3.2: Create ConversationThread Component

-> Delegate: `/ui-ux-pro-max` -- Create `<linkedout-fe>/src/components/search/ConversationThread.tsx`

Design from HTML mockup (`conversation-history-followup.html`):

**Structure per turn:**
```
[User message]
  [Avatar (28px, pastel-lavender, initials)] [Bubble (bg-subtle, border, rounded-[10px_10px_10px_3px])]
[System response]
  [offset 38px left] [Icon (28px, accent-light, search icon)] [Bubble (accent-light, border-pastel-lavender-mid)]
    [Text with <strong> for numbers]
    [Result summary chips row]
[Turn divider] (line + "Turn N" label)
```

**Visual details:**
- User bubble: `bg-bg-subtle border border-border rounded-[10px_10px_10px_3px] px-3 py-2 text-[0.9rem] max-w-[620px]`
- System bubble: `bg-berry-accent-light border border-pastel-lavender-mid rounded-[10px_10px_10px_3px] px-3 py-2 text-sm text-berry-accent-dark max-w-[620px]`
- Result summary chips: `rs-chip` style -- `font-mono text-[0.6875rem] bg-bg-surface border border-pastel-lavender-mid rounded-full px-2 py-0.5 text-berry-accent-dark`
- Removal chips: `bg-pastel-peach border-pastel-peach-mid text-[#8B4A5E]`
- Turn divider: thin line + mono label "Turn N" at 0.5 opacity
- User avatar: "SJ" initials (hardcoded for now)

Props:
```typescript
interface ConversationThreadProps {
  turns: ConversationTurn[];
}
```

After delegation, review:
- User messages right-of-avatar, system messages indented
- Chips render inline in system bubbles
- Removal chips have rose styling
- Turn dividers between turns

### Step 3.3: Create FollowUpBar Component

-> Delegate: `/ui-ux-pro-max` -- Create `<linkedout-fe>/src/components/search/FollowUpBar.tsx`

Design from mockup:
- Input: `flex-1 border-2 border-border rounded-[10px] px-3.5 py-2.5 text-[0.9375rem] focus:border-berry-accent focus:ring-[3px] focus:ring-berry-accent-light`
- Placeholder: "Refine, narrow, exclude, ask a question about these results..."
- Send button: `w-10 h-10 rounded-lg bg-berry-accent` with send icon (white arrow)
- Layout: flex row with `gap-2`

Props:
```typescript
interface FollowUpBarProps {
  onSubmit: (message: string) => void;
  isLoading?: boolean;
}
```

Internal state: controlled input. Submit on Enter or click send.

### Step 3.4: Create HintChips Component

-> Delegate: `/ui-ux-pro-max` -- Create `<linkedout-fe>/src/components/search/HintChips.tsx`

Design from mockup:
- Row of clickable pills: `border border-border bg-bg-surface rounded-full px-2.5 py-1 text-xs text-text-secondary`
- Each chip has a type label prefix: `font-mono text-[0.6rem] uppercase tracking-[0.05em] text-text-tertiary mr-0.5` (e.g., "NARROW", "RANK", "EXCLUDE", "BROADEN", "ASK")
- Hover: `border-berry-accent text-berry-accent-dark bg-berry-accent-light`
- Click: calls `onSelect(action)` which populates the follow-up bar

Props:
```typescript
interface HintChipsProps {
  actions: SuggestedAction[];
  onSelect: (action: SuggestedAction) => void;
}
```

### Step 3.5: Create ExcludedBanner Component

-> Delegate: `/ui-ux-pro-max` -- Create `<linkedout-fe>/src/components/search/ExcludedBanner.tsx`

Design from mockup:
- Banner: `bg-pastel-peach border border-pastel-peach-mid rounded-lg px-3 py-2 text-[0.8125rem] text-[#8B4A5E]`
- Layout: flex row -- X icon + description text + "Undo" button (ml-auto)
- Undo button: `text-xs text-berry-accent hover:underline`

Props:
```typescript
interface ExcludedBannerProps {
  exclusionState: ExclusionState;
  onUndo: () => void;
}
```

Only render when `excluded_count > 0`.

### Step 3.6: Extend useStreamingSearch for Conversation Turns

Edit `<linkedout-fe>/src/hooks/useStreamingSearch.ts`:

Add to state:
```typescript
conversationTurns: ConversationTurn[];
suggestedActions: SuggestedAction[];
exclusionState: ExclusionState | null;
resultMetadata: ResultMetadata | null;
```

Add new SSE event handling for `conversation_turn` event type. The backend may send conversation metadata as part of the `done` event or as a separate event -- check the actual backend SSE format. At minimum:

1. Add `"conversation_turn"` to `SearchEventType`
2. In the event handler, when a conversation turn response arrives, extract `result_summary_chips`, `suggested_actions`, `exclusion_state`, `result_metadata`
3. Append to `conversationTurns` array
4. Update `suggestedActions` and `exclusionState`

**Important:** The exact SSE event format depends on the backend. Read the SSE proxy route and backend search controller to understand what events are sent. The backend may bundle conversation metadata into the existing `done` event payload, or send it as a separate event type.

### Step 3.7: Wire Conversation UI into SearchPageContent

Edit `<linkedout-fe>/src/components/search/SearchPageContent.tsx`:

Major layout change when session has turns:

```
[SearchBar (initial search)] OR [FollowUpBar (during active multi-turn)]
[ConversationThread (above results, if turns > 0)]
[FollowUpBar (below thread)]
[HintChips (below follow-up bar)]
[ExcludedBanner (above results, if excluded_count > 0)]
[ResultsList]
```

Logic:
1. Import new components: `ConversationThread`, `FollowUpBar`, `HintChips`, `ExcludedBanner`
2. Track conversation turns in state (from `useStreamingSearch` or separate state)
3. When `turnCount > 0`:
   - Show `ConversationThread` above results
   - Replace top `SearchBar` with `FollowUpBar`
   - Show `HintChips` below follow-up bar
   - Show `ExcludedBanner` if exclusion state has excluded profiles
4. Follow-up submission: call `search(message, activeSessionId)` which sends to the backend with session_id
5. Hint chip click: populate follow-up input and optionally auto-submit

### Step 3.8: Update ResultsList Header

Edit `<linkedout-fe>/src/components/search/ResultsList.tsx`:

When `resultMetadata` is available, update the results count header:
```tsx
<p className="font-mono text-xs text-text-tertiary">
  {resultMetadata
    ? `${resultMetadata.count} results${resultMetadata.sort_description ? ` · ${resultMetadata.sort_description}` : ""}`
    : isStreaming
      ? `Loading... ${results.length} so far`
      : `Showing ${start + 1}-${end} of ${sorted.length} results`}
</p>
```

Add `resultMetadata?: ResultMetadata` to `ResultsListProps`.

## Verification

### Automated Tests (permanent)

No new test files (visual verification).

### Validation Scripts (temporary)

```bash
cd <linkedout-fe> && npx tsc --noEmit
cd <linkedout-fe> && npm run dev
```

### Manual Checks

1. Search for a query -- first turn shows in conversation thread (user bubble + system response)
2. System response includes result summary chips inline (e.g., "22 results", "8 Inner Circle")
3. Follow-up bar appears below the conversation thread
4. Type a follow-up message (e.g., "remove anyone at FAANG") and submit
5. New turn appends to thread with user bubble + system response
6. Result summary chips in system response show changes (e.g., "-9 FAANG")
7. Turn dividers appear between turns with "Turn N" labels
8. Hint chips render below follow-up bar (e.g., "NARROW Only SF / NYC", "RANK By affinity")
9. Click a hint chip -- populates follow-up input
10. If exclusion occurred, excluded banner appears: "9 people at FAANG excluded" with Undo button
11. Results header updates with count + sort description from `result_metadata`
12. Compare visually against `<linkedout-fe>/docs/design/conversation-history-followup.html`

### Success Criteria
- [ ] Conversation thread renders with multi-turn history (user + system bubbles)
- [ ] Result summary chips render inline in system bubbles
- [ ] Removal chips have rose styling
- [ ] Turn dividers with "Turn N" labels between turns
- [ ] Follow-up bar appears after first turn
- [ ] Follow-up submission triggers search with session_id
- [ ] Hint chips render from `suggested_actions`
- [ ] Hint chip click populates follow-up input
- [ ] Excluded banner shows when `excluded_count > 0` with undo button
- [ ] Results header shows count + sort description from metadata
- [ ] ThinkingState reused for turn processing
- [ ] TypeScript compiles with no errors
- [ ] Visual match to HTML mockup

## Execution Notes

- The conversation thread should auto-scroll to the bottom when a new turn is added. Use `useRef` + `scrollIntoView` on the thread container.
- The backend SSE event format for conversation turns needs to be verified. Read:
  - `./src/linkedout/intelligence/controllers/search_controller.py` -- the search endpoint that produces SSE
  - `./src/linkedout/intelligence/contracts.py` -- `ConversationTurnResponse` model
- If the backend does not yet send conversation metadata in SSE events, the frontend may need to fetch it separately via `GET /sessions/{id}` after each turn completes.
- The "Undo" button on the excluded banner: for now, call `search("undo last exclusion", sessionId)` or show a toast saying "Undo sent". The backend handles undo via conversation.
- Keep existing facet panel working alongside the conversation UI. Facets may need to update based on `ConversationTurnResponse.facets` in a future iteration.
- The user avatar shows "SJ" initials -- this is hardcoded for the demo user. In production, derive from `app_user_id`.

**Spec-linked files:** Read `./docs/specs/linkedout_intelligence.collab.md` and `./docs/specs/search_sessions.collab.md` for conversation turn behavior and response format.
