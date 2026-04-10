# Fix: Run freshness check in manual mode before showing Fetch button

## Context

**Original design intent:** Manual mode was deliberately backend-free on navigation — Voyager data was fetched and displayed, but no backend calls were made until the user clicked "Fetch". This kept manual mode a zero-side-effect browsing experience.

**The bug:** Because `processVoyagerData()` returns early in manual mode (before `checkFreshness()`), the side panel always falls back to the `not_saved` badge. Every profile shows "Save to LinkedOut" — even profiles already saved and fresh in the backend. The Fetch button label is wrong, and clicking it for an already-fresh profile wastes a rate-limited save operation.

**Why this matters now:** As the user's LinkedOut database grows, most browsed profiles will already be saved. Showing "Save to LinkedOut" for every profile creates noise and erodes trust in the extension's awareness of its own data.

## Approach: Parallel freshness check

The freshness check is a lightweight read (`GET /crawled-profiles?linkedin_url=...&limit=1`) — not a write. Adding it to navigation doesn't violate the manual-mode principle of "no side effects until user clicks."

Start `checkFreshness()` at `URL_CHANGED` time (in `handleUrlChanged()`), not after Voyager data arrives. The freshness check only needs the LinkedIn URL, not Voyager data, so it can run **in parallel** with the Voyager fetch. This also avoids a UX flash where the "Save to LinkedOut" button briefly appears then disappears when the sequential freshness check resolves:

```
URL_CHANGED
  → checkFreshness() starts (backend call)          ← parallel
  → content script fetches Voyager API               ← parallel
  → both resolve
  → processVoyagerData() uses already-resolved freshness
  → correct badge shown immediately
```

## Changes (all in `extension/entrypoints/background.ts`)

### 1. New ephemeral state (~line 50)

Add the in-flight freshness promise. Badge status is folded into `lastParsedResult` (no separate variable):

```ts
let freshnessPromise: Promise<FreshnessResult> | null = null;

// Extend lastParsedResult to include resolved badge status:
let lastParsedResult: {
  profile: NonNullable<ReturnType<typeof parseVoyagerProfile>>;
  profileId: string;
  profileData: ProfileDisplayData;
  resolvedStatus?: {
    badgeStatus: ProfileBadgeStatus;
    crawledProfileId?: string;
    staleDays?: number;
  };
} | null = null;
```

### 2. Start freshness check in `handleUrlChanged()` (~line 627)

When a profile URL is detected, kick off `checkFreshness()` immediately:

```ts
async function handleUrlChanged(data: UrlChanged): Promise<void> {
  const { url } = data;
  currentTabUrl = url;
  cancelPipeline();
  lastParsedResult = null;
  freshnessPromise = null;

  if (!isLinkedInProfilePage(url)) {
    currentProfileId = null;
    sendProfileStatus('idle');
    return;
  }

  const profileId = extractProfileId(url);
  if (!profileId) return;
  currentProfileId = profileId;

  sendProfileStatus('fetching', { linkedinUrl: url });
  await sendRateLimitUpdate();

  // Start freshness check in parallel with Voyager fetch
  const linkedinUrl = `https://www.linkedin.com/in/${profileId}`;
  freshnessPromise = checkFreshness(linkedinUrl).catch((err) => {
    if (err instanceof BackendUnreachable) return { exists: false, offline: true } as FreshnessResult;
    return { exists: false } as FreshnessResult;
  });
}
```

### 3. Use resolved freshness in manual-mode branch of `processVoyagerData()` (~lines 170-187)

Replace the early return with:

```ts
// Always send profile data for display
sendProfileStatus('ready', {
  profileName, profileHeadline: profile.headline, linkedinUrl, profileData,
});

if (enrichmentMode === 'manual') {
  // Await the freshness check started at URL_CHANGED time
  const freshness = freshnessPromise ? await freshnessPromise : null;

  // Preserve offline detection: if freshness came back with offline flag, surface it
  if (freshness && 'offline' in freshness && freshness.offline) {
    setOffline(true);
  } else if (freshness) {
    markBackendReachable();
  }

  if (!freshness || !freshness.exists) {
    lastParsedResult!.resolvedStatus = { badgeStatus: 'not_saved' };
    sendProfileStatus('ready', {
      badgeStatus: 'not_saved',
      profileName, profileHeadline: profile.headline, linkedinUrl, profileData,
    });
  } else if (freshness.staleDays < STALENESS_DAYS) {
    // Backfill enrichment if missing
    if (!freshness.profile.has_enriched_data) {
      try { await enrichProfileBackend(freshness.id, toEnrichPayload(profile)); } catch {}
    }
    lastParsedResult!.resolvedStatus = { badgeStatus: 'up_to_date', crawledProfileId: freshness.id, staleDays: freshness.staleDays };
    sendProfileStatus('skipped', {
      badgeStatus: 'up_to_date',
      profileName, profileHeadline: profile.headline, linkedinUrl,
      crawledProfileId: freshness.id, profileData, staleDays: freshness.staleDays,
    });
  } else {
    lastParsedResult!.resolvedStatus = { badgeStatus: 'stale', crawledProfileId: freshness.id, staleDays: freshness.staleDays };
    sendProfileStatus('ready', {
      badgeStatus: 'stale',
      profileName, profileHeadline: profile.headline, linkedinUrl,
      crawledProfileId: freshness.id, profileData, staleDays: freshness.staleDays,
    });
  }
  processingProfileId = null;
  return;
}
```

### 4. Side panel reconnect (~lines 757-766)

Use `lastParsedResult.resolvedStatus` when sending cached profile:

```ts
if (lastParsedResult && lastParsedResult.profileId === currentProfileId) {
  const { profile, profileData, resolvedStatus } = lastParsedResult;
  sendProfileStatus(resolvedStatus ? (resolvedStatus.badgeStatus === 'up_to_date' ? 'skipped' : 'ready') : 'ready', {
    profileName: profileData.name,
    profileHeadline: profile.headline,
    linkedinUrl: profileData.linkedinUrl,
    profileData,
    ...(resolvedStatus && {
      badgeStatus: resolvedStatus.badgeStatus,
      crawledProfileId: resolvedStatus.crawledProfileId,
      staleDays: resolvedStatus.staleDays,
    }),
  });
  sendRateLimitUpdate();
}
```

### 5. Also set `lastParsedResult.resolvedStatus` in auto-mode `enrichProfile()` 

After each terminal state in `enrichProfile()` (saved_today, up_to_date, stale, save_failed), set `lastParsedResult!.resolvedStatus` so reconnect works for auto mode too.

### 6. Extend `FreshnessResult` type (in `extension/lib/backend/client.ts`)

Add `offline` flag to the not-found branch so the catch handler can signal backend-unreachable:

```ts
export type FreshnessResult =
  | { exists: false; offline?: boolean }
  | { exists: true; id: string; staleDays: number; profile: CrawledProfileResponse };
```

### 7. Unit tests for coordination logic (new test file)

Add tests that mock `checkFreshness` and simulate key sequences:

1. **Fresh profile:** URL_CHANGED → VOYAGER_DATA_READY → badge shows `up_to_date`
2. **Stale profile:** URL_CHANGED → VOYAGER_DATA_READY → badge shows `stale`
3. **Not found:** URL_CHANGED → VOYAGER_DATA_READY → badge shows `not_saved`
4. **Backend unreachable:** URL_CHANGED → VOYAGER_DATA_READY → `setOffline(true)` called, badge shows `not_saved`
5. **Rapid navigation:** second URL_CHANGED before first freshness resolves → first promise discarded, second used

No changes needed to messages.ts, FetchButton.tsx, or App.tsx — the existing badge status values and button visibility logic already handle `up_to_date`, `stale`, and `not_saved` correctly.

## Verification
1. Open extension on a profile that IS saved and fresh → button should be hidden, badge shows "Up to date"
2. Open extension on a profile that IS saved but stale → button shows "Update Profile"
3. Open extension on a profile that does NOT exist → button shows "Save to LinkedOut"
4. Disconnect backend → offline bar shown, badge shows "Not saved" with offline context (not silent fallback)
5. Open extension on linkedin.com/in/gshailesh/ → should show "Up to date" (no button)
6. Close and reopen side panel → badge persists correctly
7. Click a profile link (SPA navigation) → freshness runs in parallel, correct badge shows quickly

## Review Decisions

> Decisions from plan review have been **incorporated into the plan above**.
> This section is kept as a record of the review discussion.

### 2026-04-05 -- Plan Review

**Section: Architecture**
- Issue #1: `.catch()` on `freshnessPromise` swallows `BackendUnreachable`, losing offline detection -> Decision: Catch but preserve error type. Add `offline?: boolean` to the `{ exists: false }` branch of `FreshnessResult`. In `processVoyagerData`, check `offline` flag to call `setOffline(true)` instead of `markBackendReachable()`. Verification step 4 should show offline bar, not just "Save to LinkedOut".

**Section: Code Quality**
- Issue #2: `lastResolvedStatus` introduces a second piece of ephemeral state alongside `lastParsedResult`, increasing stale-state surface -> Decision: Fold `resolvedStatus` into `lastParsedResult` as an optional field (`resolvedStatus?: { badgeStatus, crawledProfileId?, staleDays? }`). One variable to clear on navigation, one place to check on reconnect.

**Section: Tests**
- Issue #3: No automated tests for the parallel freshness + Voyager coordination logic -> Decision: Add unit tests that mock `checkFreshness` and simulate key sequences: (1) URL_CHANGED then VOYAGER_DATA_READY with fresh profile, (2) stale profile, (3) not-found profile, (4) backend unreachable, (5) rapid navigation (second URL_CHANGED before first freshness resolves).

**Section: Performance**
- (No issues raised — parallel design is a net improvement)
