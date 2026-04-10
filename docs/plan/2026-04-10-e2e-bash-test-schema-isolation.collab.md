# E2E Bash Test Schema Isolation

## Context

Both bash E2E scripts (`tests/installation/test_e2e_flow.sh` and
`test_upgrade_path.sh`) run against the raw `DATABASE_URL` with zero
isolation — no test schema, no cleanup. They pollute the real database and
cannot safely run in parallel.

The Python integration tests (`backend/tests/integration/conftest.py`) already
solve this with per-run schema isolation. The bash scripts should do the same.

Running the tests on a fresh database exposed three pre-existing bugs that must
be fixed first.

## Pre-existing bugs to fix

### Bug 1: `env.py` — `backend_config.DATABASE_URL` attribute doesn't exist
- **File:** `backend/migrations/env.py:58`
- **Problem:** References `backend_config.DATABASE_URL` (uppercase), but the
  pydantic field is `database_url` (lowercase). `validation_alias` only
  affects input parsing, not attribute access.
- **Fix:** Change to `backend_config.database_url`
- **Status:** DONE

### Bug 2: Alembic configparser chokes on `%` in URL
- **File:** `backend/migrations/env.py:58`
- **Problem:** `config.set_main_option()` passes through Python's
  `configparser`, which treats `%` as interpolation syntax. URLs with
  `%3D`/`%2C` (from search_path options) raise `ValueError`.
- **Fix:** `.replace('%', '%%')` before passing to `set_main_option`
- **Status:** DONE

### Bug 3: RLS blocks all writes on fresh database
- **File:** `backend/migrations/versions/001_baseline.py:684-704`
- **Problem:** `FORCE ROW LEVEL SECURITY` is enabled on connection,
  crawled_profile, experience, education, profile_skill — but the only
  policies are `FOR SELECT`. With no INSERT/UPDATE/DELETE policies and FORCE
  active, PostgreSQL denies all writes, even from the table owner.
- **Impact:** `linkedout import-connections` fails on any fresh database.
- **Fix:** Add permissive `FOR ALL` policies (or `FOR INSERT`, `FOR UPDATE`,
  `FOR DELETE`) that allow the `linkedout` owner to write. The RLS intent is
  to restrict SELECTs to the current user's data, not to block writes.
  Simplest: one `FOR ALL` policy per table that permits writes when
  `app.current_user_id` is set.

### Bug 4: E2E scripts merge stderr into JSON stdout (`2>&1`)
- **Files:** Both test scripts
- **Problem:** `$(linkedout status --json 2>&1)` captures stderr logs into
  stdout, corrupting the JSON that assertion helpers try to parse.
- **Fix:** Use `2>/dev/null` for commands whose stdout is parsed as JSON.
- **Status:** DONE

## Schema isolation plan

### 1. `tests/installation/_test_schema_helpers.sh` (new)

Shared helper sourced by both scripts. Two functions:

**`setup_test_schema`**
- Saves `ORIGINAL_DATABASE_URL`, generates `TEST_SCHEMA_NAME=e2e_test_<epoch>_<pid>`
- Drops-then-creates schema via `psql`
- Creates empty `alembic_version` table in test schema (prevents Alembic from
  finding stale revision in `public`)
- Builds schema-qualified URL: `?options=-csearch_path%3D<schema>%2Cpublic`
- Re-exports `DATABASE_URL`

**`cleanup_test_schema`**
- `DROP SCHEMA IF EXISTS ... CASCADE` via `psql` using original URL
- Guarded with `|| true`, safe to call multiple times

**Status:** DONE

### 2. `test_e2e_flow.sh` modifications

- Source helper, call `setup_test_schema`, add `cleanup_test_schema` to trap
- Run `linkedout migrate` after config.yaml write (test schema starts empty)
- Use `2>/dev/null` for JSON-parsed commands

**Status:** DONE (except Bug 3 blocks Step 2)

### 3. `test_upgrade_path.sh` modifications

- Source helper, call `setup_test_schema`, add `cleanup_test_schema` to trap
- Use `2>/dev/null` for JSON-parsed commands

**Status:** DONE

## Remaining: Bug 3 — RLS write policy fix

The `linkedout` role has `rolbypassrls = false`. The migration enables `FORCE
ROW LEVEL SECURITY` with SELECT-only policies. This blocks all INSERT/UPDATE
/DELETE, breaking `import-connections` and any other write operation.

**Fix in `001_baseline.py`:** After the SELECT policies, add a write policy:

```sql
-- For connection table:
CREATE POLICY app_user_write ON connection FOR ALL
  USING (true)
  WITH CHECK (app_user_id = NULLIF(current_setting('app.current_user_id', TRUE), ''));

-- For profile-linked tables:
CREATE POLICY user_profiles_write ON <table> FOR ALL
  USING (true)
  WITH CHECK (true);
```

The `WITH CHECK` on connection ensures writes set the correct `app_user_id`.
Profile tables don't need a `WITH CHECK` constraint since they're linked via
foreign key.

Since this is migration `001_baseline` (the only migration, never run on this
machine), editing it directly is safe — no existing databases to worry about.

## Files summary

| File | Action | Status |
|---|---|---|
| `tests/installation/_test_schema_helpers.sh` | Create | DONE |
| `tests/installation/test_e2e_flow.sh` | Edit | DONE |
| `tests/installation/test_upgrade_path.sh` | Edit | DONE |
| `backend/migrations/env.py` | Fix attribute + configparser | DONE |
| `backend/migrations/versions/001_baseline.py` | Add RLS write policies | TODO |

## Verification

1. Run `bash tests/installation/test_e2e_flow.sh` — all steps pass
2. Run `bash tests/installation/test_upgrade_path.sh` — all steps pass
3. `psql` query confirms no `e2e_test_*` schemas remain after
4. `precommit-tests` (unit + integration) still pass
