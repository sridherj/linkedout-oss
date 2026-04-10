# Sub-phase 1: Enhanced Result Cards with Highlighted Attributes

> **Pre-requisite:** Read `./docs/execution/linkedout-quality-fe/_shared_context.md` before starting this sub-phase.

## Objective

Add LLM-driven highlight chips to profile result cards, showing up to 3 query-aware attribute pills per card with color-coded tiers. Enhance the unenriched card state with a proper dimmed appearance and "Enrich" prompt bar. Add a "View profile" button and click handler to cards (preparing for FE3 slide-over integration). This is the foundation sub-phase -- every other frontend feature builds on or interacts with these cards.

## Dependencies
- **Requires completed:** None -- this is the first sub-phase
- **Assumed codebase state:** Existing frontend with `ProfileCard.tsx`, `ProfileCardUnenriched.tsx`, `ProfileCardSkeleton.tsx`, types in `search.ts`

## Scope
**In scope:**
- Extend `ProfileResult` type with `highlighted_attributes` and `explanation` fields
- Create `HighlightChip` component with 3 color tiers
- Add highlight chips zone to `ProfileCard` between current role and why_this_person box
- Add "View profile" button to card footer
- Add `onClick` prop to `ProfileCard` for slide-over integration
- Enhance `ProfileCardUnenriched` with 0.85 opacity, "Enrich" prompt bar, dimmed why-box
- Update `ProfileCardSkeleton` with chip zone placeholder
- Update `useStreamingSearch` to handle `highlighted_attributes` in explanations event
- Visually match the HTML mockup at `<linkedout-fe>/docs/design/result-cards-highlighted-attributes.html`

**Out of scope (do NOT do these):**
- Profile slide-over panel (SP2b)
- Session management (SP2a)
- Conversation thread UI (SP3)
- Backend changes -- all APIs are already implemented
- Facet panel changes
- Changing the search bar or search flow

## Files to Create/Modify

| File | Action | Current State |
|------|--------|---------------|
| `<linkedout-fe>/src/types/search.ts` | Modify | Has `ProfileResult` without `highlighted_attributes` |
| `<linkedout-fe>/src/components/profile/HighlightChip.tsx` | Create | Does not exist |
| `<linkedout-fe>/src/components/profile/ProfileCard.tsx` | Modify | Has avatar, name, badges, headline, why_this_person, footer -- no chips, no onClick |
| `<linkedout-fe>/src/components/profile/ProfileCardUnenriched.tsx` | Modify | Has opacity-75, checkbox, initials, enrich button -- needs richer dimmed state |
| `<linkedout-fe>/src/components/profile/ProfileCardSkeleton.tsx` | Modify | Has basic skeleton -- needs chip zone placeholder |
| `<linkedout-fe>/src/hooks/useStreamingSearch.ts` | Modify | Handles `explanations` event with string values -- needs to handle `ProfileExplanation` objects |
| `<linkedout-fe>/src/components/search/ResultsList.tsx` | Modify | Renders cards -- needs to pass `onClick` prop through |

## Detailed Steps

### Step 1.1: Extend TypeScript Types

Edit `<linkedout-fe>/src/types/search.ts`:

```typescript
export interface HighlightedAttribute {
  text: string;      // e.g. "IC -> PM in 18 mo"
  color_tier: number; // 0=lavender, 1=rose, 2=sage
}

export interface ProfileResult {
  // ... existing fields ...
  highlighted_attributes?: HighlightedAttribute[];
}
```

Add `HighlightedAttribute` interface and add `highlighted_attributes?: HighlightedAttribute[]` to `ProfileResult`.

### Step 1.2: Create HighlightChip Component

-> Delegate: `/ui-ux-pro-max` -- Create `<linkedout-fe>/src/components/profile/HighlightChip.tsx`

Design spec from HTML mockup:
- Pill shape: `rounded-full` (9999px radius)
- Layout: 5px dot + text, `gap-[5px]`, `px-[10px] py-1`
- Font: `text-xs font-medium` (0.75rem, 500 weight)
- Border: 1px solid, color varies by tier
- Color mapping:
  - Tier 0 (lavender): `bg-pastel-lavender border-pastel-lavender-mid text-[#5B4A7A]`
  - Tier 1 (rose): `bg-pastel-peach border-pastel-peach-mid text-[#8B4A5E]`
  - Tier 2 (sage): `bg-pastel-sage border-pastel-sage-mid text-[#6B5A42]`
- Dot: 5px circle, `currentColor` at 0.6 opacity
- Hover: background transitions to mid variant (e.g., `pastel-lavender` -> `pastel-lavender-mid`)

Props: `{ text: string; colorTier: number }`

After delegation, review the output to verify:
- Color mapping matches design system tokens exactly
- Hover states work
- Dot renders correctly

### Step 1.3: Add Highlight Chips to ProfileCard

-> Delegate: `/ui-ux-pro-max` -- Modify `<linkedout-fe>/src/components/profile/ProfileCard.tsx`

Changes:
1. Import `HighlightChip` and `HighlightedAttribute` type
2. Add `onClick?: () => void` prop to `ProfileCardProps`
3. Add a `highlights` zone between the current role section and the why_this_person box:
   ```tsx
   {/* Highlight chips */}
   {result.highlighted_attributes && result.highlighted_attributes.length > 0 && (
     <div className="mt-2.5 flex flex-wrap gap-1.5">
       {result.highlighted_attributes.slice(0, 3).map((attr, i) => (
         <HighlightChip key={i} text={attr.text} colorTier={attr.color_tier} />
       ))}
     </div>
   )}
   ```
4. Add "View profile" button in the footer `card-actions` div:
   ```tsx
   <button
     type="button"
     onClick={(e) => { e.stopPropagation(); onClick?.(); }}
     className="rounded-sm px-2 py-1 font-ui text-xs text-text-secondary transition-colors hover:bg-berry-accent-light hover:text-berry-accent-dark"
   >
     View profile
   </button>
   ```
5. Make the outer card div clickable: add `onClick` handler, add `cursor-pointer` class
6. Keep ALL existing content unchanged (avatar, badges, headline, location, role, why_this_person, footer)

After delegation, review:
- Max 3 chips enforced via `.slice(0, 3)`
- onClick handler has `e.stopPropagation()` on footer buttons to prevent card click bubble
- Existing visual structure is preserved

### Step 1.4: Enhance ProfileCardUnenriched

-> Delegate: `/ui-ux-pro-max` -- Modify `<linkedout-fe>/src/components/profile/ProfileCardUnenriched.tsx`

Changes per HTML mockup:
1. Change card opacity from `opacity-75` to `opacity-[0.85]`
2. Add hover: `hover:opacity-100`
3. Add "Enrich to see career arc, key signals, and full history" prompt bar where chips would go:
   ```tsx
   <div className="mt-2 flex items-center justify-between gap-2 rounded-md bg-bg-subtle px-2.5 py-[7px]">
     <span className="text-xs text-text-tertiary">Enrich to see career arc, key signals, and full history</span>
     <button className="shrink-0 rounded-sm bg-berry-accent px-2.5 py-1 font-ui text-[0.6875rem] text-white transition-colors hover:bg-berry-accent-hover">
       Enrich
     </button>
   </div>
   ```
4. If `why_this_person` exists, render at 0.7 opacity:
   ```tsx
   {result.why_this_person && (
     <p className="mt-2 rounded-md bg-berry-accent-light px-3 py-2 text-sm text-berry-accent-dark opacity-70">
       {result.why_this_person}
     </p>
   )}
   ```
5. Keep existing checkbox, initials avatar, name, role, connected_at, and existing enrich button logic

After delegation, review:
- Opacity values match spec (0.85 card, 0.7 why-box)
- Enrich prompt bar is visually distinct from chip zone
- Existing enrichment flow (confirm step) still works

### Step 1.5: Update ProfileCardSkeleton

Add chip zone skeleton between role line and footer:
```tsx
{/* Chip zone placeholder */}
<div className="mt-2.5 flex gap-1.5">
  <div className="h-6 w-28 rounded-full bg-bg-subtle" />
  <div className="h-6 w-24 rounded-full bg-bg-subtle" />
</div>
```

### Step 1.6: Update useStreamingSearch for Highlighted Attributes

Edit `<linkedout-fe>/src/hooks/useStreamingSearch.ts`:

The backend `explanations` event now sends `ProfileExplanation` objects (with `explanation` string and `highlighted_attributes` array) instead of plain strings. Update the `explanations` case:

```typescript
case "explanations":
  if (event.payload) {
    const explanations = event.payload as Record<string, {
      explanation: string;
      highlighted_attributes?: { text: string; color_tier: number }[];
    }>;
    setState((prev) => ({
      ...prev,
      results: prev.results.map((r) =>
        explanations[r.connection_id]
          ? {
              ...r,
              why_this_person: explanations[r.connection_id].explanation,
              highlighted_attributes: explanations[r.connection_id].highlighted_attributes ?? [],
            }
          : r
      ),
    }));
    // Also patch any buffered results
    resultsBufferRef.current = resultsBufferRef.current.map((r) =>
      explanations[r.connection_id]
        ? {
            ...r,
            why_this_person: explanations[r.connection_id].explanation,
            highlighted_attributes: explanations[r.connection_id].highlighted_attributes ?? [],
          }
        : r
    );
  }
  break;
```

**Important:** The backend may still send plain string explanations (backwards compatibility). Add a type guard:
```typescript
const expl = explanations[r.connection_id];
const isStructured = typeof expl === 'object' && expl !== null && 'explanation' in expl;
```

### Step 1.7: Update ResultsList to Pass onClick

Edit `<linkedout-fe>/src/components/search/ResultsList.tsx`:

1. Add `onCardClick?: (connectionId: string) => void` to `ResultsListProps`
2. Pass `onClick={() => onCardClick?.(result.connection_id)}` to `ProfileCard`

### Step 1.8: Wire onCardClick in SearchPageContent

Edit `<linkedout-fe>/src/components/search/SearchPageContent.tsx`:

1. Add state: `const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);`
2. Pass `onCardClick={setSelectedProfileId}` to `ResultsList`
3. This state will be consumed by SP2b (profile slide-over) -- for now it just sets state

## Verification

### Automated Tests (permanent)

No new test files for this sub-phase (frontend tests are visual). Verification is manual and via design review.

### Validation Scripts (temporary)

```bash
# Build check -- no TypeScript errors
cd <linkedout-fe> && npx tsc --noEmit

# Dev server starts without errors
cd <linkedout-fe> && npm run dev
```

### Manual Checks

1. Open the app and search for any query
2. Wait for results to stream in and explanations event to arrive
3. Verify highlight chips appear on enriched cards (up to 3 per card)
4. Verify chip colors match: lavender (tier 0), rose (tier 1), sage (tier 2)
5. Hover over chips -- background should transition to mid variant
6. Verify unenriched cards show 0.85 opacity with "Enrich" prompt bar
7. Verify unenriched cards' why_this_person box is at 0.7 opacity
8. Verify "View profile" button appears in enriched card footer
9. Verify clicking a card or "View profile" does not crash (state updates silently for now)
10. Compare visually against HTML mockup at `<linkedout-fe>/docs/design/result-cards-highlighted-attributes.html`

### Success Criteria
- [ ] `HighlightChip` component renders with 3 color tiers matching design system
- [ ] Max 3 chips per card enforced
- [ ] Enriched cards show chips between role and why_this_person
- [ ] Unenriched cards show 0.85 opacity with "Enrich" prompt bar
- [ ] Why_this_person on unenriched cards at 0.7 opacity
- [ ] "View profile" button in enriched card footer
- [ ] Card click sets selectedProfileId state
- [ ] TypeScript compiles with no errors (`npx tsc --noEmit`)
- [ ] Existing card features (badges, avatar, why_this_person, LinkedIn link) unaffected
- [ ] Visual match to HTML mockup

## Execution Notes

- The `explanations` event from the backend may arrive after initial results stream in. Chips will appear when explanations arrive -- this is expected behavior.
- The backend `highlighted_attributes` field may be empty or missing for some profiles. Handle gracefully (no chips rendered).
- If the backend still sends string explanations (old format), the type guard ensures backward compatibility.
- The `onClick` prop on ProfileCard is optional -- cards without it still work as before.
- Do NOT change the search flow or facet panel -- only card rendering and types.

**Spec-linked files:** This sub-phase modifies types matching the intelligence spec. Read `./docs/specs/linkedout_intelligence.collab.md` to verify the `ProfileExplanation` contract matches.
