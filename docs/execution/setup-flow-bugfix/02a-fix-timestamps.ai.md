# Sub-phase 02a: Fix Raw SQL Missing Timestamps

## Metadata
- **Depends on:** nothing
- **Blocks:** 04-spec-updates, 05-tests
- **Estimated scope:** 1 file modified
- **Plan section:** Phase 2a (Issue 10)

## Context

Read `_shared_context.md` for timestamp requirements.

## Task

**File:** `backend/src/linkedout/setup/user_profile.py`, lines 138-141

The INSERT into `crawled_profile` omits `created_at` and `updated_at`, which are NOT NULL
with Python-side-only defaults (no `server_default`). Hits `NotNullViolation`.

**Fix:** Add both columns to the INSERT:
```sql
INSERT INTO crawled_profile
  (id, linkedin_url, public_identifier, data_source, created_at, updated_at)
VALUES (:id, :url, :pid, 'setup', NOW(), NOW())
```

## Verification
After user_profile step:
```sql
SELECT created_at, updated_at FROM crawled_profile WHERE data_source='setup';
```
Both return non-null timestamps.

## Completion Criteria
- [ ] INSERT includes `created_at` and `updated_at` with `NOW()`
- [ ] No lint errors
