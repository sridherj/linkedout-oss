# Decision: Chrome Extension Activity Log Stored Locally

**Date:** 2026-04-04
**Status:** Accepted
**Context:** linkedout-chrome-plugin — Phase 4a (activity log UI) design

## Question

Where should the Chrome extension activity log live — in the LinkedOut backend (PostgreSQL) or in local browser storage (`chrome.storage.local`)?

## Key Findings

- The backend only receives calls when a profile is successfully saved — skips, errors, and rate-limit blocks are never sent and would require new API endpoints to capture
- The activity log's primary consumer is the extension's own UI panel, not any backend analytics workflow
- `chrome.storage.local` is scoped per-extension and persists across browser restarts; it is the idiomatic Chrome storage mechanism for extension-local state
- Adding backend storage would require schema changes, new API surface, and network calls for events that only matter to the local user

## Decision

Activity log entries are stored in `chrome.storage.local` via `log.ts`. Each entry captures: timestamp, event type (saved / skipped / error / rate-limited), profile URL, profile name, and a human-readable reason. The side panel's Activity tab reads directly from local storage.

Backend is NOT involved in activity logging.

## Implications

- Log is device-local — not synced across the user's machines (acceptable for v1)
- A log rotation strategy (cap at N entries or 30 days) should be implemented in `log.ts` to prevent unbounded storage growth
- If cross-device sync becomes a requirement in v2, the log schema is simple enough to POST to a backend endpoint

## References

- Plan: `<prior-project>/taskos/goals/linkedout-chrome-plugin/plan_post_spike.collab.md` (Phase 2a, Phase 4a)
- Spec: `./docs/specs/chrome_extension.collab.md`
