# FE4: Result Cards with Highlighted Attributes

## Context
Backend WhyThisProfile improvement is complete (SP3b). Search responses now include `highlighted_attributes` with `color_tier` for each result. Existing `ProfileCard.tsx` and `ProfileCardUnenriched.tsx` need enhancement to render these LLM-driven highlight chips and handle the unenriched state properly.

## Important: File Resolution
- **Frontend code lives at:** `<linkedout-fe>`
- **Backend code and specs live at:** `.` (also accessible via `.`)
- If a referenced file is not found at one location, check `.`, `.`, or `<prior-project>`
- **Leverage the `/ui-ux-pro-max` skill** for all UI implementation work

## Design Reference
- **HTML mockup:** `<linkedout-fe>/docs/design/result-cards-highlighted-attributes.html`
- **Design system:** `<linkedout-fe>/docs/design/linkedout-design-system.md`

## Backend Contracts
- **HighlightedAttribute:** `./src/linkedout/intelligence/contracts.py`
  - `{attribute_type, label, color_tier}` — attribute_type is one of: skill_match, company_match, career_trajectory, network_proximity, tenure_signal, seniority_match
  - `color_tier`: 0 = lavender, 1 = rose, 2 = sage
  - Max 3 per card
- **ProfileExplanation:** `./src/linkedout/intelligence/contracts.py` — includes `highlighted_attributes` list + `why_this_person` text
- **Intelligence spec:** `./docs/specs/linkedout_intelligence.collab.md`

## Frontend Patterns (match these)
- **Existing card structure:** `<linkedout-fe>/src/components/profile/ProfileCard.tsx` — already has: avatar (40px with InitialsAvatar fallback), name + headline + location, AffinityBadge (score-based color: pastel-mint/peach/subtle), DunbarBadge (tier-based: pastel-lavender/sage/peach/subtle), current role, why_this_person box (berry-accent-light bg), footer with connected_at + LinkedIn link
- **Styling:** Tailwind with design tokens. Card uses `rounded-[10px] border border-border bg-bg-surface` with hover `border-berry-accent`
- **Types:** `<linkedout-fe>/src/types/search.ts` — `ProfileResult` needs extending with `highlighted_attributes?: HighlightedAttribute[]` and `is_enriched?: boolean`
- **UI primitives:** `<linkedout-fe>/src/components/ui/badge.tsx` — may be useful for chips

## Existing Frontend Files to Modify
- `<linkedout-fe>/src/components/profile/ProfileCard.tsx` — add highlight chips zone between current role and why_this_person box. Add click-to-open slide-over. Card currently has no `onClick` handler
- `<linkedout-fe>/src/components/profile/ProfileCardUnenriched.tsx` — enhance with proper dimmed state (0.85 opacity), "Enrich" prompt bar replacing chip zone, why-box at 0.7 opacity
- `<linkedout-fe>/src/components/profile/ProfileCardSkeleton.tsx` — may need update for new card layout with chip zone
- `<linkedout-fe>/src/types/search.ts` — extend `ProfileResult` with highlighted_attributes

## Activities

### FE4.1 Highlight Chip Component
- New component: `HighlightChip.tsx` in `<linkedout-fe>/src/components/profile/`
- Colored pill with dot indicator + short text
- Color mapping: lavender (color_tier 0), rose (color_tier 1), sage (color_tier 2)
- Colors must match design system palette

### FE4.2 Enhanced ProfileCard
- **Fixed scaffold (always rendered):** avatar + name + affinity badge + Dunbar tier badge + headline + location + role summary + Why This Person box + footer (connected date + LinkedIn + "View profile")
- **LLM-driven zone:** 2-3 `HighlightChip` components from `highlighted_attributes`
- Max 3 chips per card
- Click card opens profile slide-over (FE3)

### FE4.3 Unenriched Profile State
- Card dimmed to 0.85 opacity
- No highlight chips displayed
- "Enrich" prompt bar replaces chip zone — invites user to request enrichment
- Why This Person box at lower opacity (0.7)
- Existing `ProfileCardUnenriched.tsx` should be enhanced, not replaced

### FE4.4 Card-to-SlideOver Integration
- Clicking a card (or "View profile") opens the FE3 slide-over panel
- Selected card gets visual highlight, others dim to 0.45
- Pass `connection_id` to slide-over for API fetch

## Verification
- [ ] Highlight chips render with correct colors for each tier
- [ ] Max 3 chips per card enforced
- [ ] Unenriched cards show dimmed state with "Enrich" bar
- [ ] Card click opens slide-over (if FE3 is implemented)
- [ ] Design matches HTML mockup at `<linkedout-fe>/docs/design/result-cards-highlighted-attributes.html`
- [ ] Follows design system at `<linkedout-fe>/docs/design/linkedout-design-system.md`
