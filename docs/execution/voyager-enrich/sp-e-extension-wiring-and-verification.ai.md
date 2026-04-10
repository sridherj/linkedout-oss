# Sub-phase E: Extension Wiring + Spec Update + Verification

**Effort:** 30-45 minutes
**Dependencies:** SP-B (backend endpoint must work) + SP-D (extension mapper/client must exist)
**Working directory:** `<linkedout-fe>` (extension) and `.` (spec + verification)
**Shared context:** `_shared_context.md`

---

## Objective

Wire `enrichProfile()` into the extension's save flow in `background.ts`, add the fresh-but-unenriched backfill path, update the Chrome extension spec, and verify end-to-end with a real profile.

## What to Do

### 1. Wire Enrichment into `background.ts`

**File:** `<linkedout-fe>/extension/entrypoints/background.ts`

Add imports:
```ts
import { enrichProfile } from '../lib/backend/client';
import { toEnrichPayload } from '../lib/profile/mapper';
```

There are 3 "done" paths where the profile is saved. In each, call `enrichProfile()` **before** sending the "done" status (Q7: await enrich before badge). Catch and log failures (Q11: always show "Saved today"):

**Path 1 — New profile create** (after `createProfile()` returns `newId`):
```ts
try {
  await enrichProfile(newId, toEnrichPayload(profile));
} catch (err) {
  console.warn('[enrichProfile] Failed:', err);
  await appendLogAndNotify({
    timestamp: new Date().toISOString(),
    action: 'error',
    profileName, linkedinUrl,
    reason: `Enrichment failed: ${err}`,
  });
}
// THEN send done status
```

**Path 2 — 409 race → update** (after `updateProfile()` with retry ID):
Same pattern — `try { await enrichProfile(...) } catch { log }` before done status.

**Path 3 — Stale → update** (after `updateProfile()` with freshness ID):
Same pattern.

**Path 4 — Fresh but unenriched (Q10: backfill):**
In the "skip" path where the profile is fresh (< 30 days), add a check:
```ts
if (!freshness.profile.has_enriched_data) {
  try {
    await enrichProfile(freshness.id, toEnrichPayload(profile));
  } catch (err) {
    console.warn('[enrichProfile] Backfill failed:', err);
  }
}
```
This fires before sending `skipped` / `up_to_date` status.

**Important:** `toCrawledProfilePayload()` in `mapper.ts` does NOT set `has_enriched_data`. The backend `enrich()` method sets it to `true`. This ensures correct state even when enrichment fails.

> Read `background.ts` carefully to identify the exact locations of these 3+1 paths. Line numbers in the plan (234, 257, 302, 281-299) are approximate — find the actual save flow logic.

### 2. Fresh-but-Unenriched Test

**File:** `<linkedout-fe>/extension/entrypoints/__tests__/background.test.ts` (or appropriate test file)

Test: when `freshness.profile.has_enriched_data === false` and profile is fresh → `enrichProfile()` is called (Q10).
Test: when `has_enriched_data === true` and profile is fresh → `enrichProfile()` is NOT called.

### 3. Update Chrome Extension Spec

**File:** `./docs/specs/chrome_extension.collab.md`

Update Decision #4 (or relevant section about data enrichment) to reflect:
- New `POST /crawled-profiles/{id}/enrich` endpoint
- Extension calls enrich after save
- Backfill path for fresh-but-unenriched profiles

### 4. End-to-End Verification

Run the verification command from the shared context against a real profile:

```bash
# Start the backend if not running
cd . && python main.py &

# Call enrich on Manjusha's profile
curl -X POST http://localhost:8001/crawled-profiles/cp_NW0DkPyIpcn_69BK4jRZz/enrich \
  -H "Content-Type: application/json" \
  -H "X-App-User-Id: usr_sys_001" \
  -d '{
    "experiences": [
      {"position": "Human Resources Consultant", "company_name": "ValueMomentum", "is_current": true},
      {"position": "Technical Recruiter (Product Hiring)", "company_name": "KANARY STAFFING", "start_year": 2022, "start_month": 4, "end_year": 2024, "end_month": 1}
    ],
    "educations": [
      {"school_name": "Andhra University", "degree": "MBA", "field_of_study": "HR"},
      {"school_name": "NTR University", "degree": "Bachelor", "field_of_study": "Pharmacy"}
    ],
    "skills": ["Talent Acquisition", "HR Operations", "Recruitment", "Sourcing", "Employee Relations", "LinkedIn Recruiter", "Technical Recruiting"]
  }'
```

Verify response: `{"experiences_created": 2, "educations_created": 2, "skills_created": 7}`

Then verify DB state (use `/postgres` skill or direct SQL):
- 2 experience rows, 2 education rows, 7 skill rows
- `has_enriched_data = true`
- `search_vector` is non-null
- `embedding` is non-null

## Verification

```bash
# Extension type check
cd <linkedout-fe> && npx tsc --noEmit

# Extension tests
npx vitest run extension/entrypoints/__tests__/background.test.ts

# Full backend test suite still passes
cd . && pytest tests/ -v --timeout=30
```

## Files Modified/Created

| File | Action |
|------|--------|
| `<linkedout-fe>/extension/entrypoints/background.ts` | Wire enrichProfile in 3 done paths + backfill |
| `<linkedout-fe>/extension/entrypoints/__tests__/background.test.ts` | Add fresh-but-unenriched test |
| `./docs/specs/chrome_extension.collab.md` | Update Decision #4 for enrich endpoint |
