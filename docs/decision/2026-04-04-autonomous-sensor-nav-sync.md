# Decision: Autonomous Sensor pattern for side panel navigation sync

**Date:** 2026-04-04
**Status:** Accepted
**Context:** LinkedOut Chrome Extension — side panel navigation sync

## Question
How should the Chrome extension detect LinkedIn profile page changes and trigger Voyager API fetches, given that LinkedIn suggestion links cause full-page navigation (destroying content scripts)?

## Key Findings
- LinkedIn suggestion/search result links trigger full-page navigation, not SPA pushState
- Full-page nav destroys the old content script context entirely
- New content scripts re-inject at `document_idle`, which is after `tabs.onUpdated` fires
- The previous architecture (service worker detects URL change -> sends FETCH_PROFILE_REQUEST to content script) had a race condition: message sent before content script was ready
- Three designs were evaluated:
  - **Design A (Ready handshake):** Content script sends "I'm ready", SW responds with fetch command. Works but adds complexity.
  - **Design B (Content script polls):** Content script queries SW for pending work. Over-engineered.
  - **Design C (Autonomous Sensor):** Content script always fetches Voyager on URL change. SW just updates state. Simplest.

## Decision
Adopted Design C (Autonomous Sensor). The content script autonomously fetches Voyager data whenever it detects a LinkedIn profile URL, without waiting for instructions from the service worker. The service worker's `handleUrlChanged` only updates tab state (status, profileUrl) — it never triggers fetches.

**Why:** The content script is the only component that knows when it's injected and ready to access the page DOM/Voyager API. Placing the fetch trigger there eliminates the timing race entirely. It's also the simplest design — fewer messages, fewer states, fewer failure modes.

## Implications
- Content script is stateless and autonomous — always fetches on profile URL detection
- Service worker caches `lastParsedResult` to avoid re-fetching when user clicks manual Fetch button
- `RETRY_FETCH` message exists for challenge recovery (SW -> CS), but it's "conditions changed, re-check" not "fetch this profile"
- New `'ready'` status in the state machine for the window between fetch completion and enrichment decision
- Manual mode Fetch button sends `ENRICH_PROFILE` to SW (which uses cached result), not `FETCH_PROFILE_REQUEST` to CS

## References
- `~/workspace/linkedout-fe/extension/src/voyager.content.ts`
- `~/workspace/linkedout-fe/extension/src/background.ts`
- `~/workspace/linkedout-fe/extension/src/messages.ts`
- `~/workspace/linkedout-fe/extension/src/App.tsx`
- `~/workspace/linkedout-fe/extension/src/bridge.content.ts`
