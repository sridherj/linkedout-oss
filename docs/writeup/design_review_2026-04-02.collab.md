# Design Review: LinkedOut Search Results Page

**Date:** 2026-04-02
**URL:** `localhost:3000/?q=can+you+tell+me+people+who+have+been+director+in+product+companies+and+have+moved+from+IT+and+also+likely+hire`
**Classifier:** APP UI (workspace-driven, data-dense, task-focused)
**Branch:** master

---

## First Impression

The site communicates **functional competence with warm aesthetics**. The Berry Fields color palette and Fraunces serif give it editorial warmth, which is the right tone for "your network is personal, not a spreadsheet."

The cards are doing too much. Each card is a wall of text: name, headline, location, role (duplicate of headline), a 5-line explanation paragraph, chips, date, actions. At ~360px per card, you see 1.5 cards per viewport. For a search results page, that kills scan-ability.

The first 3 things my eye goes to are: **the query bubble** (good, grounds me), **the explanation paragraph** (too heavy, competes with the name), **the monospace role line** (redundant with headline above it).

One word: **verbose**.

---

## Findings

### FINDING-001: Duplicate headline/role information (HIGH)

Every card shows the headline twice. `ProfileCard.tsx:88` renders `result.headline` truncated in Fraunces 14px. `ProfileCard.tsx:111` renders `result.current_position at result.current_company_name` in Fragment Mono 12px. For most profiles, these contain nearly identical text. Example: User A's "#Immediate joiner | Looking for a opportunity as a Service Desk Analyst..." appears in both places.

This wastes ~40px of vertical space per card. Across 19 cards that's 760px of duplicate content. The monospace role line adds value only when `current_position` differs from the headline.

**Fix:** Conditionally render the mono role line only when it adds new information (when current_position + company isn't a substring of the headline).

---

### FINDING-002: Explanation paragraphs are too long for scan-ability (HIGH)

The `why_this_person` box is 4-5 lines of prose per card (~80 words). Example: "This is a weak match for your query because User A has IT support experience, but there is no director-level role or evidence of working in product companies. His background is in Service Desk Analyst at Wipro and System Engineer at Precision Infomatic, which aligns with the 'moved from IT' part only in a technical support sense. There is also no clear hiring responsibility shown on the profile."

For a results list, this is a reading assignment, not a signal. The chips ("Wipro service desk", "IT support profile") already carry the key signals. The paragraph should be 1 line max, with an expandable "Read more" for the full explanation. Something like: "Weak match: IT support background, no director-level product company role."

**Fix:** Truncate `why_this_person` to ~15 words with `line-clamp-1` and an expand toggle. Or better, have the backend return a short summary alongside the full explanation.

---

### FINDING-003: No visual differentiation by match quality (HIGH)

"Weak match" and "strong match" cards are visually identical. User B ("strong match on the likely-hire dimension") and User A ("weak match for your query") use the same `bg-berry-accent-light` box. The user scanning 19 results has no quick way to tell which cards deserve attention without reading every paragraph.

**Fix:** Parse match strength from the explanation (or have the backend return it as a field). Use different box colors:
- Strong: `bg-pastel-sage` with a subtle green-ish left accent
- Partial: `bg-berry-accent-light` (current, keep as default)
- Weak: `bg-bg-subtle` with muted text

---

### FINDING-004: Follow-up conversation is broken (CRITICAL)

Submitting a follow-up query via the FollowUpBar ("only show me people in Bengaluru") destroys the entire results state and lands on "No results found" with no search bar, no results, no way to recover. The URL doesn't update to reflect the follow-up query.

Root cause from code: `handleFollowUp` at `SearchPageContent.tsx:210` calls `search(message, activeSessionId)` which resets `results: []` in state. When the stream response fails or returns no results for the refinement query, the page shows the empty state. The original results are gone. There's no previous-turn preservation.

Even when the backend is healthy, the UX is wrong: submitting a follow-up should NOT blow away the current results until new results arrive. The previous results should remain visible (maybe dimmed) while the new stream loads.

---

### FINDING-005: Session switcher visibility is inconsistent (MEDIUM)

At 960px viewport, the session switcher ("19 sessions" + "New Search" buttons) appeared in the initial load. At 1440px, those buttons disappeared from the DOM. On a subsequent reload, "20 sessions" + "+ New Search" appeared at both sizes. The session count changed (19 vs 20) between loads, and the styling is inconsistent: one view shows plain text buttons, the other shows a pill with a green dot + purple gradient "New Search" button.

This suggests either the session switcher renders conditionally based on state that's not stable, or there are competing component versions.

---

### FINDING-006: Cards are too tall for results scanning (MEDIUM)

Average card height: 360px. At 923px viewport height minus header/search chrome (~200px), you see ~2 cards. For 19 results, that's 10 screens of scrolling. Competitive search products show 5-8 results per screen.

The fix is a combination of findings 001, 002, and 003: remove the duplicate headline, collapse the explanation to 1 line, and the cards drop to ~200px, giving 3-4 cards per screen. That's a 2x improvement in scan-ability.

---

### FINDING-007: Auth error state design is good but lacks recovery (POLISH)

The "Auth Error: Session Expired" state with the keyhole illustration is well-designed. Warm illustration, clear message, thinking steps still visible. The only gap: no retry button or "Sign in again" action. It's a dead end.

---

### FINDING-008: Facet filter pills lack selected state (MEDIUM)

The facet filters (Bengaluru (8), Mumbai (2), etc.) are plain text pills. There's no visual distinction between active and inactive filters. For faceted search, selected filters should have a filled/highlighted state with an "x" to clear.

---

### FINDING-009: Mobile cards are even more verbose (POLISH)

On mobile (375px), the Affinity and Dunbar badges drop below the name into a separate row. This is handled correctly with responsive classes. But the explanation paragraph is even harder to read on a narrow screen. The `line-clamp` fix from FINDING-002 matters even more on mobile.

---

## Scores

| Category | Grade | Notes |
|----------|-------|-------|
| Visual Hierarchy | C | Cards too tall, explanation competes with name for attention |
| Typography | B+ | Fraunces + Fragment Mono is the right system. Well-applied. |
| Color & Contrast | B+ | Berry Fields palette is warm and coherent. Good chip colors. |
| Spacing & Layout | B | Grid works, cards well-structured, but too much vertical space |
| Interaction States | B | Card hover works. Missing: facet selected state |
| Responsive | B- | Works but not designed for mobile. Cards too tall. |
| Content Quality | D | Duplicate headlines, verbose explanations, no match strength signal |
| AI Slop | A | Zero slop detected. This looks intentionally designed. |
| Motion | B | Hover transitions smooth. Thinking animation is good. |
| Performance | C | Stream takes 20+ seconds. "Loading... 19 so far" sits a while. |

**Design Score: C+**
**AI Slop Score: A** (clean, no slop patterns detected)

---

## Priority Fixes

1. **CRITICAL: Fix follow-up conversation flow** -- don't blow away results on follow-up submit. Keep previous results visible until new ones arrive. (`SearchPageContent.tsx:210`, `useStreamingSearch.ts:119`)
2. **HIGH: Collapse explanation to 1-line + expand** -- biggest scan-ability win (`ProfileCard.tsx:119-123`)
3. **HIGH: Remove duplicate headline** -- suppress mono role when it matches headline (`ProfileCard.tsx:110-116`)
4. **HIGH: Add match strength visual signal** -- different box color for strong/partial/weak (`ProfileCard.tsx:119`)
5. **MEDIUM: Facet selected state** -- show which filters are active (`FacetPanel.tsx`)
6. **MEDIUM: Auth error recovery** -- add retry/sign-in action button

---

## Summary

The card density problem (findings 001+002+003) is the design story here. Fix those three and the page goes from "reading assignment" to "scannable results list." The follow-up conversation bug (finding 004) is a functional blocker for multi-turn search. The design system (typography, color, illustration) is solid. The problem is information architecture, not aesthetics.
