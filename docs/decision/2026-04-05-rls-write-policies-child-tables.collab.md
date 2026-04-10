# RLS Write Policies for Experience/Education/ProfileSkill Tables

**Date:** 2026-04-05
**Status:** Decided

## Question

Why do INSERTs into `experience`, `education`, and `profile_skill` fail with `InsufficientPrivilege` when RLS is enabled?

## Key Findings

- All four tables (`crawled_profile`, `experience`, `education`, `profile_skill`) have `relrowsecurity = true` and `relforcerowsecurity = true`.
- `crawled_profile` had an `allow_all` policy (`FOR ALL USING (true) WITH CHECK (true)`) — writes worked fine.
- The three child tables only had a `user_profiles` SELECT policy (connection-based visibility). **No INSERT/UPDATE/DELETE policies existed.**
- With RLS enabled and no write policy, PostgreSQL denies all writes by default — even for table owners when `relforcerowsecurity` is set.
- This was latent: the Apify pipeline (`PostEnrichmentService._extract_experiences`) hadn't run since RLS was enabled, so the gap was never hit until the new `ProfileEnrichmentService.enrich()` endpoint was tested.

## Decision

Added `allow_all` policies on all three child tables:

```sql
CREATE POLICY allow_all_experience ON experience FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY allow_all_education ON education FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY allow_all_profile_skill ON profile_skill FOR ALL USING (true) WITH CHECK (true);
```

This matches the existing `crawled_profile` pattern. The SELECT-level `user_profiles` policy remains for read filtering (connection-based visibility).

## Implications

- The `enrich()` endpoint and Apify pipeline can now write structured rows.
- Any future tables with RLS enabled must have explicit write policies — RLS defaults to deny.
- Consider auditing other tables for the same gap if RLS was batch-enabled.
