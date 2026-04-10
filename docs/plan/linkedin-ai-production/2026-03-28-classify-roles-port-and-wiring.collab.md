# Port classify-roles: Classification Engine, DB Wiring, and CLI

## Overview

Port the regex-based role classification script from second-brain (`linkedin-intel/scripts/classify_roles.py`) into the linkedout project's `dev_tools` module. The old script classified 36K role aliases with 80% coverage across 45K unique titles using a first-match-wins regex strategy. The new version adapts it to the linkedout schema (singular table names, nanoid IDs, `sqlalchemy.text()` instead of raw psycopg, `db_session_manager` for sessions). This unblocks `backfill-seniority` and `compute-affinity` which currently operate on 0 role_alias rows.

No exploration phase was needed -- the source code, tests, and schema mapping are fully understood from the high-level plan.

## Operating Mode

**HOLD SCOPE** -- The high-level plan explicitly scopes Part 1 to "port classify-roles" with specific files, SQL approaches, and verification steps. No signals for expansion or reduction. Rigorous adherence to the stated port scope.

## Sub-phase 1: Pure Classification Functions and Tests

**Outcome:** `classify_seniority()` and `classify_function()` exist as pure functions in `src/dev_tools/classify_roles.py`, importable and tested. 75 parametrized test cases pass. Zero DB dependency in this sub-phase.

**Dependencies:** None

**Estimated effort:** 1 session (~2 hours)

**Verification:**
- `pytest tests/dev_tools/test_classify_roles.py -v` -- all 75 cases pass
- Import `from dev_tools.classify_roles import classify_seniority, classify_function` succeeds
- Functions are pure (no DB imports at module level in the classification section)

Key activities:

- Create `src/dev_tools/classify_roles.py` with the two rule lists (`SENIORITY_RULES`, `FUNCTION_RULES`) and two pure functions (`classify_seniority`, `classify_function`). Copy regex patterns verbatim from `<prior-project>/linkedin-intel/scripts/classify_roles.py` (lines 17-86). Adapt type hints from `str | None` to `Optional[str]` if the project targets Python <3.10, otherwise keep as-is.
- Create `tests/dev_tools/test_classify_roles.py` with all 75 parametrized test cases. Port from `<prior-project>/linkedin-intel/scripts/test_classify_roles.py`. Adjust import path from `from classify_roles import ...` to `from dev_tools.classify_roles import ...`.
- Ensure `tests/dev_tools/__init__.py` exists (create if missing) so pytest discovers the test module.
- Run the test suite to verify all 75 cases pass.

**Design review:**
- Naming: `classify_seniority` / `classify_function` match the old script exactly -- no deviation.
- Spec consistency: `role_alias` entity has `seniority_level` (String(100)) and `function_area` (String(100)). The classification output values (e.g., "c_suite", "engineering") are short strings well within 100 chars. No conflict.
- Architecture: Pure functions with no side effects is the correct pattern for testability. The old script's approach is proven.

## Sub-phase 2: DB Operations -- role_alias Population and Experience/Profile Updates

**Outcome:** The `main(dry_run=False)` function exists in `classify_roles.py`. When called, it: (1) fetches distinct titles from `experience.position` UNION `crawled_profile.current_position`, (2) classifies them in-memory, (3) upserts into `role_alias` with `ON CONFLICT`, (4) bulk updates `experience.seniority_level/function_area`, (5) updates `crawled_profile` from current experience + direct role_alias fallback. Dry-run mode executes steps 1-2 only and prints stats.

**Dependencies:** Sub-phase 1 (pure functions must exist)

**Estimated effort:** 1-2 sessions (~3-4 hours)

**Verification:**
- `rcv2 db classify-roles --dry-run` prints title count, classification rate, seniority/function distribution
- `rcv2 db classify-roles` populates `role_alias` and updates `experience` + `crawled_profile`
- `psql $DATABASE_URL -c "SELECT COUNT(*) FROM role_alias;"` shows expected row count
- `psql $DATABASE_URL -c "SELECT seniority_level, COUNT(*) FROM role_alias WHERE seniority_level IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;"` shows distribution
- `rcv2 db backfill-seniority --dry-run` shows matches (confirms role_alias data is usable)

Key activities:

- **Step 1 query -- UNION DISTINCT titles from two tables.** Use `sqlalchemy.text()`:
  ```sql
  SELECT DISTINCT title FROM (
      SELECT position AS title FROM experience WHERE position IS NOT NULL
      UNION
      SELECT current_position AS title FROM crawled_profile WHERE current_position IS NOT NULL
  ) t
  ```
  This sources from BOTH tables so `backfill_seniority` can match `crawled_profile.current_position` values too. Use `db_session_manager.get_session(DbSessionType.WRITE)` for the session (same pattern as `backfill_seniority.py`).

- **Step 2 -- in-memory classification loop.** Iterate titles, call `classify_seniority()` and `classify_function()`, collect results. For dry-run mode: print total titles, classified count, percentage, seniority distribution, function distribution, then return 0.

- **Step 3 -- INSERT role_alias with ON CONFLICT.** Use batched raw SQL with `sqlalchemy.text()`. Generate `ra_` prefixed nanoid IDs via `Nanoid.make_nanoid_with_prefix('ra')`. Key SQL:
  ```sql
  INSERT INTO role_alias (id, alias_title, canonical_title, seniority_level, function_area, is_active, version, created_at, updated_at)
  VALUES (:id, :alias_title, :canonical_title, :seniority_level, :function_area, true, 1, NOW(), NOW())
  ON CONFLICT (alias_title) DO UPDATE SET
      seniority_level = EXCLUDED.seniority_level,
      function_area = EXCLUDED.function_area,
      updated_at = NOW()
  ```
  Note: Must include all BaseEntity required fields (`id`, `is_active`, `version`, `created_at`, `updated_at`) since we're using raw SQL, not ORM. Batch in groups of 500-1000 for performance.

- **Step 4 -- UPDATE experience via temp table JOIN.** The COPY protocol from the old script is psycopg-specific. Adapt to SQLAlchemy-compatible approach: CREATE TEMP TABLE, batch INSERT into temp table, then UPDATE JOIN. SQL:
  ```sql
  CREATE TEMP TABLE _role_map (title TEXT, seniority TEXT, function_area TEXT)
  ```
  Then batch insert classifications, then:
  ```sql
  UPDATE experience e
  SET seniority_level = rm.seniority,
      function_area = rm.function_area
  FROM _role_map rm
  WHERE e.position = rm.title
    AND (e.seniority_level IS NULL OR e.function_area IS NULL)
  ```

- **Step 5 -- UPDATE crawled_profile.** Two UPDATE statements:
  1. From current experience (matching the old script's `is_current = TRUE` + `start_date DESC` logic):
     ```sql
     UPDATE crawled_profile p
     SET seniority_level = sub.seniority_level,
         function_area = sub.function_area
     FROM (
         SELECT DISTINCT ON (crawled_profile_id)
             crawled_profile_id, seniority_level, function_area
         FROM experience
         WHERE is_current = TRUE
           AND (seniority_level IS NOT NULL OR function_area IS NOT NULL)
         ORDER BY crawled_profile_id, start_date DESC NULLS LAST, id DESC
     ) sub
     WHERE sub.crawled_profile_id = p.id
       AND p.has_enriched_data = TRUE
     ```
  2. Direct role_alias fallback for profiles without a current experience match:
     ```sql
     UPDATE crawled_profile p
     SET seniority_level = ra.seniority_level,
         function_area = ra.function_area
     FROM role_alias ra
     WHERE ra.alias_title = p.current_position
       AND p.seniority_level IS NULL
       AND p.current_position IS NOT NULL
     ```

- **Print a distribution report** at the end (matching the old script's output style): seniority counts, function counts, total rows affected per step.

- **Error handling:** Wrap the entire operation in a single transaction (the `db_session_manager` context manager handles this). If any step fails, the whole transaction rolls back. Print the error and return exit code 1.

**Design review:**
- Spec consistency (CLI Commands spec): The `db classify-roles` command follows the established pattern: `--dry-run` flag, lazy import in CLI, exit code propagation. Matches `fix-none-names`, `backfill-seniority`, `compute-affinity` patterns exactly.
- Spec consistency (Data Model spec): `role_alias` table has `alias_title` (unique), `canonical_title`, `seniority_level`, `function_area`. The INSERT matches these columns. `experience` has `seniority_level` and `function_area`. `crawled_profile` has `seniority_level`, `function_area`, `current_position`, `has_enriched_data`. All columns referenced exist per entity definitions.
- Error paths: What if `experience` table is empty (no profiles loaded yet)? Step 1 returns 0 titles from the experience UNION, Step 3-4 are no-ops. Script should handle gracefully with a "No titles found" message and return 0.
- Error paths: What if `role_alias` already has data from a prior run? `ON CONFLICT` handles this -- upserts are idempotent. Step 4-5 WHERE clauses check `IS NULL` so already-classified rows are skipped.
- Architecture: Raw SQL with `sqlalchemy.text()` is appropriate for 40K+ bulk operations. The spec deviation note in `linkedout_crud.collab.md` acknowledges shared entities use custom patterns. Dev tools scripts are not CRUD endpoints -- they're batch operations where raw SQL is the correct choice.
- Security: No user input reaches SQL -- all parameterized via `:param` bindings. No path traversal concerns.
- Naming: `_role_map` temp table name is descriptive. Column names in temp table match the entity columns they feed into.

## Sub-phase 3: CLI Wiring and End-to-End Verification

**Outcome:** `rcv2 db classify-roles` is a working CLI command. The full pipeline (classify -> backfill-seniority -> compute-affinity) runs successfully. CLI spec is updated.

**Dependencies:** Sub-phase 2

**Estimated effort:** 0.5 session (~1 hour)

**Verification:**
```bash
# CLI help works
rcv2 db classify-roles --help

# Dry run
rcv2 db classify-roles --dry-run

# Real run
rcv2 db classify-roles

# Downstream commands unblocked
rcv2 db backfill-seniority --dry-run   # should show matches
rcv2 db compute-affinity --dry-run     # should confirm ready

# DB spot-check
psql $DATABASE_URL -c "SELECT COUNT(*) FROM role_alias;"
psql $DATABASE_URL -c "SELECT seniority_level, COUNT(*) FROM role_alias WHERE seniority_level IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;"

# Unit tests still pass
pytest tests/dev_tools/test_classify_roles.py -v
```

Key activities:

- Add the `db classify-roles` command to `src/dev_tools/cli.py`. Follow the exact pattern from `db_fix_none_names` / `db_backfill_seniority`:
  ```python
  @db.command(name='classify-roles')
  @click.option('--dry-run', is_flag=True, help='Classify and report only, do not write')
  def db_classify_roles(dry_run):
      """Classify titles into seniority/function, populate role_alias, update experience + crawled_profile."""
      from dev_tools.classify_roles import main as classify_main
      exit_code = classify_main(dry_run=dry_run)
      if exit_code != 0:
          sys.exit(exit_code)
  ```
- Add backward-compatible alias: `classify_roles_command = db_classify_roles` at the bottom of cli.py with the other aliases.
- Update the CLI Commands spec (`docs/specs/cli_commands.collab.md`):
  - Add `src/dev_tools/classify_roles.py` to `linked_files`
  - Add `db classify-roles` behavior entry under DB Group:
    ```
    - **db classify-roles**: Given experience and crawled_profile rows with position titles. Running the command classifies titles via regex into seniority_level and function_area, populates role_alias via upsert, and bulk updates experience and crawled_profile. Verify `--dry-run` reports classification stats without writing, and real run populates role_alias and updates downstream tables.
    ```
  - Bump version to 3
  - Delegate: `/taskos-update-spec` with the above changes. Review output for accuracy.
- Run `precommit-tests` to confirm nothing is broken.

**Design review:**
- Spec consistency: Adding to the DB Group follows the existing pattern. The behavior description matches the established format (Given/Running/Verify).
- Naming: `classify-roles` uses kebab-case consistent with `fix-none-names`, `backfill-seniority`, `compute-affinity`.
- Architecture: Lazy import pattern (`from dev_tools.classify_roles import main as classify_main`) matches all other db commands.
- No flags.

## Sub-phase 4: Run V1 Pipeline (GATE — blocks Phase 2 and Phase 3)

**Outcome:** The full V1 pipeline runs successfully: `classify-roles` populates `role_alias` and updates `experience` + `crawled_profile`, `backfill-seniority` propagates seniority to remaining profiles, `compute-affinity` produces baseline V1 affinity scores and Dunbar tiers for all connections. Baseline scores exist before any enrichment or V2 work begins.

**Dependencies:** Sub-phase 3 (CLI must be wired)

**Estimated effort:** 0.25 session (~30 minutes including spot-checks)

**GATE CONDITION:** All three commands must exit 0. If any command fails, Phase 2 and Phase 3 MUST NOT proceed. Diagnose and fix before continuing.

**Verification:**
```bash
# Step 1: Classify roles
rcv2 db classify-roles
# MUST exit 0. Verify:
psql $DATABASE_URL -c "SELECT COUNT(*) FROM role_alias;"
# Expect ~36K rows

# Step 2: Backfill seniority
rcv2 db backfill-seniority
# MUST exit 0. Verify:
psql $DATABASE_URL -c "SELECT COUNT(*) FROM crawled_profile WHERE seniority_level IS NOT NULL;"
# Expect significant coverage

# Step 3: Compute affinity (V1)
rcv2 db compute-affinity
# MUST exit 0. Verify:
psql $DATABASE_URL -c "SELECT dunbar_tier, COUNT(*) FROM connection WHERE affinity_score IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;"
# Expect all connections scored with tier distribution

# Gate check: all three succeeded
echo "V1 pipeline complete. Phase 2 and Phase 3 are unblocked."
```

Key activities:

- Run `uv pip install -r requirements.txt` to ensure the local CLI package from `pyproject.toml` is installed with the new `classify-roles` command registered.
- Run `rcv2 db classify-roles` (no `--dry-run`). Verify role_alias row count and classification rate match expectations (~80% coverage).
- Run `rcv2 db backfill-seniority`. Verify seniority_level is propagated to crawled_profile rows that have matching role_alias entries.
- Run `rcv2 db compute-affinity`. Verify all active users' connections have affinity_score, dunbar_tier, and affinity_version=1.
- Spot-check: query top-15 connections (inner_circle) for the primary user. Sanity-check that the ranking makes sense.
- If ANY command fails: investigate, fix, re-run. Do NOT proceed to Phase 2 until all three succeed.

**Design review:**
- This sub-phase produces no code changes — it's a pipeline execution and validation gate.
- The gate ensures Phase 2 (company enrichment) and Phase 3 (affinity V2) build on a known-good baseline.
- V1 scores will be overwritten by V2 later, but having them validates the pipeline works end-to-end.

## Build Order

```
Sub-phase 1 (Pure Functions + Tests) ──> Sub-phase 2 (DB Operations) ──> Sub-phase 3 (CLI + E2E) ──> Sub-phase 4 (V1 Pipeline GATE)
```

**Critical path:** Sub-phase 1 -> Sub-phase 2 -> Sub-phase 3 -> Sub-phase 4 (fully sequential, no parallelism possible)

### Cross-Phase Execution Order

This is **Phase 1 of 3** and runs first. Sub-phase 4 is a **gate** — Phase 2 and Phase 3 cannot start until the V1 pipeline completes successfully.

```
Phase 1: Classify Roles ──> Sub-phase 4: V1 Pipeline GATE ──> Phase 2: Company Enrichment ──> Phase 3: Affinity V2 ──> Run V2 + Eyeball Session
```

## Design Review Flags

| Sub-phase | Flag | Action |
|-----------|------|--------|
| Sub-phase 2 | Raw SQL INSERT must include all BaseEntity fields (id, is_active, version, created_at, updated_at) since bypassing ORM | Ensure INSERT template includes all required columns |
| Sub-phase 2 | Old script uses psycopg COPY protocol for temp table; must adapt to sqlalchemy.text() batch INSERT | Use parameterized batch INSERT instead of COPY |
| Sub-phase 2 | `has_enriched_data = TRUE` filter in Step 5 crawled_profile update -- verify this filter is still appropriate for the linkedout schema | Confirmed: `crawled_profile_entity.py` has `has_enriched_data` field, old script used same filter |
| Sub-phase 3 | CLI spec version bump required when adding new command | Include `/taskos-update-spec` in activities |

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Regex rules produce different results in new schema due to different title formatting | Med | Port tests verbatim first (Sub-phase 1). If all 75 pass, regex logic is proven. Then run dry-run to check distribution matches expectations (~80% classification rate). |
| Raw SQL INSERT misses BaseEntity fields, causing constraint violations | High | Explicitly include all required BaseEntity columns (id, is_active, version, created_at, updated_at) in the INSERT template. Test against dev DB before production. |
| TEMP TABLE approach slower than old COPY protocol | Low | 40K rows is small enough that batch INSERT to temp table is fast (<5s). Only optimize if timing exceeds 30s. |
| `backfill-seniority` still finds 0 matches after classify-roles | Med | Verify with SQL: `SELECT COUNT(*) FROM role_alias ra JOIN crawled_profile cp ON ra.alias_title = cp.current_position`. If 0, the title normalization differs between tables (whitespace, casing). Add `.strip()` to title extraction. |

## Open Questions

- **Title normalization:** ~~RESOLVED~~ Store `alias_title` as lowercase (`.strip().lower()`). All downstream lookups match on lowercase. Title-case on the fly for display if needed. This prevents casing variants from inflating the role_alias table and ensures reliable JOINs.

## Spec References

| Spec | Sections Referenced | Conflicts Found |
|------|---------------------|-----------------|
| `cli_commands.collab.md` | DB Group (all commands), Exit codes | None -- new command follows established pattern. Spec update needed (add `db classify-roles`). |
| `linkedout_data_model.collab.md` | Table Overview > role_alias, experience, crawled_profile | None -- all referenced columns exist in entities. |
| `linkedout_crud.collab.md` | Repository Layer > shared entity deviation note | None -- dev_tools scripts bypass CRUD stack intentionally (batch operations). |
