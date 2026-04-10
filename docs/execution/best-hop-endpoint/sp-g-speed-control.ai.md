# Sub-phase G: Extension — Speed Control

**Effort:** 1-2 sessions
**Dependencies:** None (independent of backend subphases)
**Working directory:** `<linkedout-fe>/extension/`
**Shared context:** `_shared_context.md`

---

## Objective

Add an extraction speed control feature to the Chrome extension. A small chip in the side panel lets users cycle through speed multipliers (1x → 2x → 4x → 8x) during mutual connection extraction.

## What to Do

### 1. Message Types

**File:** `lib/messages.ts` (or wherever message types are defined)

Add new message types:
```typescript
type SetExtractionSpeed = {
  type: 'SET_EXTRACTION_SPEED';
  multiplier: 1 | 2 | 4 | 8;
};

type ExtractionSpeedChanged = {
  type: 'EXTRACTION_SPEED_CHANGED';
  multiplier: 1 | 2 | 4 | 8;
};
```

### 2. Service Worker State

**File:** `entrypoints/background.ts`

Add speed state and message handler:
```typescript
let bestHopSpeed: 1 | 2 | 4 | 8 = 1;

// Handle SET_EXTRACTION_SPEED messages
// Update bestHopSpeed, broadcast EXTRACTION_SPEED_CHANGED back to sender
```

Pass `() => bestHopSpeed` as the `getSpeed` callback to the mutual connection extractor.

### 3. Extractor Change

**File:** `lib/mutual/extractor.ts` (or equivalent — find the file that handles page-by-page mutual connection extraction)

Add `getSpeed: () => number` callback parameter to the extraction function. Before each page sleep:

```typescript
const baseDelay = randomDelay(2000, 5000); // current human-like delay
const adjustedDelay = baseDelay / getSpeed();
await sleep(adjustedDelay);
```

**429 auto-downshift:** If LinkedIn returns a 429 response during extraction, automatically set speed to 1x and broadcast `EXTRACTION_SPEED_CHANGED`.

### 4. Side Panel UI

**File:** `BestHopPanel.tsx` (or equivalent component shown during extraction)

Add a speed chip next to the extraction progress indicator:

```
┌────────────────────────────────┐
│ Extracting mutuals  [4x]      │
│ page 3/8                       │
│ ████████████▓▓▓▓▓▓▓▓          │
│              Cancel            │
└────────────────────────────────┘
```

- Chip shows current speed: `[1x]`, `[2x]`, `[4x]`, `[8x]`
- Tapping cycles: 1x → 2x → 4x → 8x → 1x
- Sends `SET_EXTRACTION_SPEED` message to service worker on tap
- Listens for `EXTRACTION_SPEED_CHANGED` to sync display (e.g., after 429 auto-downshift)
- Only visible during extraction phase

### Speed Tiers

| Multiplier | Delay range | Notes |
|-----------|-------------|-------|
| 1x (default) | 2-5s | Current human-like behavior |
| 2x | 1-2.5s | |
| 4x | 0.5-1.25s | |
| 8x | 0.25-0.6s | Higher 429 risk |

## Verification

- Speed chip appears during extraction, cycles through multipliers on tap
- Changing speed mid-run affects the next page's delay immediately
- 429 response auto-downshifts to 1x and updates the chip display
- Default speed is 1x (no behavior change if user doesn't interact)

## What NOT to Do

- Do not persist speed preference to storage — it resets to 1x each session
- Do not show the speed chip outside of extraction phase
- Do not add a settings page for this — the chip is the only UI
