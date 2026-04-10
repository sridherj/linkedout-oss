# Sub-phase H: Extension — Best Hop Client

**Effort:** 1 session
**Dependencies:** None (independent of backend, but backend must be deployed for E2E testing)
**Working directory:** `<linkedout-fe>/extension/`
**Shared context:** `_shared_context.md`

---

## Objective

Change the extension's best-hop flow to POST structured data to the new `/best-hop` endpoint instead of building a natural language query for `/search`.

## What to Do

### 1. Find the Current Best Hop Trigger

Look for the code that currently builds a natural language query like "Find the best introduction path to {target_name} via these mutual connections: ..." and sends it to the `/search` endpoint. This is likely in a file like `lib/search.ts` or `lib/bestHop.ts`.

### 2. Replace with Structured POST

Instead of building a query string and calling `/search`, POST to `/best-hop`:

```typescript
const response = await fetch(
  `${API_BASE}/tenants/${tenantId}/bus/${buId}/best-hop`,
  {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-App-User-Id': appUserId,
    },
    body: JSON.stringify({
      target_name: targetProfile.fullName,
      target_url: targetProfile.linkedinUrl,
      mutual_urls: mutualConnections.map(m => m.linkedinUrl),
      // session_id: optional, for future resume capability
    }),
  }
);
```

### 3. SSE Parsing — No Changes Needed

The SSE event types (`session`, `thinking`, `result`, `done`) are identical to `/search`. The existing SSE parsing code should work as-is.

**One difference:** The `done` event now includes `matched` and `unmatched` counts. The UI should display these (e.g., "Found 18 of 24 mutual connections in your network").

### 4. Remove `buildQuery()` for Best Hop

Delete the code that constructed the natural language query for best-hop requests. This was the workaround for not having a dedicated endpoint.

### 5. Update Done Event Handling

When receiving the `done` event, display matched/unmatched info:

```typescript
if (event.type === 'done') {
  const { total, matched, unmatched, session_id } = event.payload;
  // Show: "Ranked {total} connections ({matched} found, {unmatched} not in network)"
}
```

## Verification

- Extension sends structured POST to `/best-hop` (verify in network tab)
- SSE stream renders results in the side panel (same as before)
- `done` event shows matched/unmatched counts
- Old `buildQuery()` code is removed
- Fallback: if `/best-hop` returns 404 (backend not deployed), show a clear error

## What NOT to Do

- Do not change SSE parsing logic — the event format is the same
- Do not add retry logic for failed requests — keep it simple for v1
- Do not change the result card rendering — `BestHopResultItem` maps to the same UI fields
