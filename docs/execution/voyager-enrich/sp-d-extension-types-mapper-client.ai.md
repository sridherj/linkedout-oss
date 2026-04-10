# Sub-phase D: Extension Types + Mapper + API Client

**Effort:** 30-45 minutes
**Dependencies:** None (fully independent — can run in parallel with SP-A/B/C)
**Working directory:** `<linkedout-fe>`
**Shared context:** `_shared_context.md`

---

## Objective

Add the frontend TypeScript types matching the backend enrichment schema, create the `toEnrichPayload()` mapper that transforms Voyager profile data into the canonical format, add the `enrichProfile()` API client function, and write tests for mapper and client.

## What to Do

### 1. Add Enrichment Types

**File:** `<linkedout-fe>/extension/lib/backend/types.ts` — append

```ts
/** Matches EnrichProfileRequestSchema from backend. */
export interface EnrichExperienceItem {
  position?: string | null;
  company_name?: string | null;
  company_linkedin_url?: string | null;
  company_universal_name?: string | null;
  employment_type?: string | null;
  start_year?: number | null;
  start_month?: number | null;
  end_year?: number | null;
  end_month?: number | null;
  is_current?: boolean | null;
  location?: string | null;
  description?: string | null;
}

export interface EnrichEducationItem {
  school_name?: string | null;
  school_linkedin_url?: string | null;
  degree?: string | null;
  field_of_study?: string | null;
  start_year?: number | null;
  end_year?: number | null;
  description?: string | null;
}

export interface EnrichProfilePayload {
  experiences: EnrichExperienceItem[];
  educations: EnrichEducationItem[];
  skills: string[];
}
```

### 2. Add `toEnrichPayload()` Mapper

**File:** `<linkedout-fe>/extension/lib/profile/mapper.ts` — add function

Key transformations:
- `VoyagerPosition.startDate` is `"2022-09"` or `"2022"` → split into year/month ints via `parseYear()` / `parseMonth()` helpers
- `VoyagerPosition.companyUrn` → resolve to company URL + universalName via `VoyagerCompany[]` array
- `!endDate` → `is_current: true`
- `educations` → map `schoolName`, `degreeName`, `fieldOfStudy`, dates
- `skills` → pass through (already flat `string[]` from Voyager parser)

Add helper functions:
- `resolveCompany(companyUrn, companies)` — match `entityUrn` in companies array
- `parseYear(dateStr)` — `"2022-09"` → 2022, `"2022"` → 2022, null → null
- `parseMonth(dateStr)` — `"2022-09"` → 9, `"2022"` → null, null → null

Import types: `VoyagerProfile`, `VoyagerCompany` from `../voyager/types`, `EnrichProfilePayload` from `../backend/types`.

See full implementation in plan Step 5b.

### 3. Add `enrichProfile()` API Client

**File:** `<linkedout-fe>/extension/lib/backend/client.ts` — add function

```ts
export async function enrichProfile(
  crawledProfileId: string,
  payload: EnrichProfilePayload,
): Promise<void> {
  await request<unknown>(
    `${API_BASE_URL}/crawled-profiles/${crawledProfileId}/enrich`,
    { method: 'POST', body: JSON.stringify(payload) },
  );
}
```

Import `EnrichProfilePayload` from `./types`. Use the existing `request()` helper and `API_BASE_URL` constant already in the file.

### 4. Mapper Test

**File:** `<linkedout-fe>/extension/lib/profile/__tests__/mapper.test.ts`

Test `toEnrichPayload()`:
- Full `VoyagerProfile` fixture → verify all fields mapped correctly
- Position → experience: `title` → `position`, `companyName` → `company_name`
- Company URL resolution from `companyUrn` via companies array
- Company `universalName` resolution
- `is_current: true` when no `endDate`
- Date parsing: `"2022-09"` → `year=2022, month=9`
- Date parsing: `"2022"` → `year=2022, month=null`
- Edge: empty positions/educations/skills → empty arrays

Check if a `VOYAGER_FULL_PROFILE` test fixture already exists — use it if available, create minimal fixture if not.

### 5. Client Test

**File:** `<linkedout-fe>/extension/lib/backend/__tests__/client.test.ts`

Test `enrichProfile()`:
- Sends POST to correct URL (`/crawled-profiles/{id}/enrich`)
- Request body shape matches `EnrichProfilePayload`
- `X-App-User-Id` header included (verify against existing `request()` helper behavior)

## Verification

```bash
cd <linkedout-fe>
# Run mapper tests
npx vitest run extension/lib/profile/__tests__/mapper.test.ts

# Run client tests
npx vitest run extension/lib/backend/__tests__/client.test.ts

# TypeScript compilation check
npx tsc --noEmit
```

## Files Modified/Created

| File | Action |
|------|--------|
| `extension/lib/backend/types.ts` | Append enrichment types |
| `extension/lib/profile/mapper.ts` | Add `toEnrichPayload()` + helper functions |
| `extension/lib/backend/client.ts` | Add `enrichProfile()` |
| `extension/lib/profile/__tests__/mapper.test.ts` | Add/update mapper tests |
| `extension/lib/backend/__tests__/client.test.ts` | Add/update client tests |
