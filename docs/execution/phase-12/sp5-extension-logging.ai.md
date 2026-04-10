# SP5: Extension Logging Integration

**Phase:** 12 — Chrome Extension Add-on
**Sub-phase:** 5 of 7
**Dependencies:** SP1 (UX Design Doc approved by SJ)
**Estimated effort:** ~45 minutes
**Shared context:** `_shared_context.md`
**Phase plan tasks:** 12F

---

## Scope

Integrate extension observability aligned with the Phase 3 logging strategy. Create the `devLog()` utility, add structured logging to backend API calls, verify rate limit logging, and implement the error badge on the extension icon.

---

## Task 12F: Extension Logging Integration

### Files to Create

#### `extension/lib/dev-log.ts`

Create the `devLog()` utility per `docs/decision/logging-observability-strategy.md` (section 13):

```typescript
export function devLog(
  level: 'debug' | 'info' | 'warn' | 'error',
  component: string,
  message: string,
  data?: unknown
): void
```

Behavior:
- Only outputs in development mode (`import.meta.env.DEV`) or when `LINKEDOUT_DEBUG=true` in extension storage
- Structured format: `[LinkedOut][{component}] {level}: {message}` + optional data
- Valid components: `background`, `voyager`, `backend-client`, `side-panel`, `options`, `rate-limiter`

### Files to Modify

#### `extension/lib/backend/client.ts`
Modify the `request()` helper to log every fetch call:
- Log: URL, method, status, duration_ms, error (if any)
- Use `devLog('info', 'backend-client', ...)` for dev console
- Append to activity log (existing `appendLog()`) for **error cases only** — don't spam the activity log with successful calls
- Read the existing code first to understand the current `request()` implementation and `appendLog()` usage

#### `extension/lib/rate-limiter.ts`
Verify existing rate limit logging includes:
- Which limit was hit (hourly vs daily)
- Current count vs limit
- Retry-after guidance
- If any of these are missing, add them using `devLog()`

#### `extension/entrypoints/background.ts`
Add error aggregation badge:
- Track error count since last side panel open
- Set badge text on extension icon: `browser.action.setBadgeText({ text: String(errorCount) })`
- Set badge color to red: `browser.action.setBadgeBackgroundColor({ color: '#dc2626' })`
- Clear badge when side panel opens (on `runtime.onConnect`)

### Decision Docs to Read

Before implementing, read:
- `docs/decision/logging-observability-strategy.md` — `devLog()` spec (section 13), backend call logging requirements, rate limit event logging, error badge
- Read current `extension/lib/backend/client.ts` to understand `request()` helper and `appendLog()` usage
- Read current `extension/lib/rate-limiter.ts` to understand existing logging
- Read current `extension/entrypoints/background.ts` to understand current event handling

### Implementation Notes

- **No correlation IDs.** Per resolved decision, correlation IDs are deferred to v2.
- `devLog()` must be zero-cost in production builds — the conditional check should be cheap
- Error badge is a simple counter, not a notification system
- Badge clears on side panel connection, not on individual error dismissal

### Verification

- [ ] `devLog()` outputs structured logs in dev mode (`import.meta.env.DEV`)
- [ ] `devLog()` is silent in production builds
- [ ] `devLog()` respects `LINKEDOUT_DEBUG=true` in extension storage
- [ ] Backend API errors are logged with status code, URL, and duration_ms
- [ ] Successful API calls are logged via `devLog()` only (not appended to activity log)
- [ ] Rate limit events include which limit, current count vs limit, and retry guidance
- [ ] Error badge appears on extension icon when errors occur
- [ ] Error badge clears when side panel opens
- [ ] Badge color is red (#dc2626)
- [ ] No console spam in production builds
