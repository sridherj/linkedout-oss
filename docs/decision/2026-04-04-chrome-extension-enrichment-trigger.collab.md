# Decision: Chrome Extension Enrichment Trigger Model

**Date:** 2026-04-04
**Status:** Accepted
**Context:** linkedout-chrome-plugin — Phase 2b (auto-enrich) design

## Question

When should the Chrome extension fetch a LinkedIn profile from the Voyager API and save it to the LinkedOut backend? Three candidate triggers were considered:
1. Always on profile navigation (regardless of mode)
2. Only on side panel open
3. Mode-aware: auto-fetch on navigate, but always fetch on panel open

## Key Findings

- Sales Navigator and Google search results allow opening 10–20 profile tabs in seconds — trigger-on-navigate in auto mode would cause mass API hits
- The side panel requires an explicit user gesture — it is a reliable intent signal
- In manual mode, the user does not want any implicit background work; panel open is still fine because it's an active choice
- The enrichment result must be available when the side panel renders, so a lazy "fetch only if panel opens" strategy in auto mode adds latency

## Decision

**Mode-aware trigger with side panel as a guaranteed fetch point:**

| Mode | Navigate to profile | Open side panel |
|------|---------------------|-----------------|
| Auto | Fetch + save (with per-profile dedup guard) | Fetch + save if not already done this session |
| Manual | Nothing | Always fetch + save |

Side panel open always ensures fresh data. Auto mode uses navigate-trigger for speed but deduplicates to avoid re-fetching within the same session. Manual mode is purely lazy — panel open is the only trigger.

## Implications

- `background.ts` must track a per-session "already fetched" set (profileUrl → boolean) to implement the dedup guard in auto mode
- The panel's loading state is needed for both modes (manual always fetches, auto may still be fetching when panel opens)
- This model is robust to tab-open spam from Sales Navigator

## References

- Plan: `<prior-project>/taskos/goals/linkedout-chrome-plugin/plan_post_spike.collab.md`
- Spec: `./docs/specs/chrome_extension.collab.md`
