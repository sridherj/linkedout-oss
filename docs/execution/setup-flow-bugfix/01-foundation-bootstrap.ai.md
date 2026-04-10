# Sub-phase 01: Foundation — Bootstrap System Records + Setup Script

## Metadata
- **Depends on:** nothing (must run first)
- **Blocks:** 02c-fix-csv-double-counting (FK records needed for verification)
- **Estimated scope:** 2 files modified
- **Plan sections:** Phase 1a, Phase 1b

## Context

Read `_shared_context.md` for table names, timestamp requirements, fixed_data imports,
and bootstrap insert order.

## Task 1a: Bootstrap system records into `setup_database()`

**File:** `backend/src/linkedout/setup/database.py`

Add `bootstrap_system_records(database_url)` that:
- Imports `SYSTEM_TENANT`, `SYSTEM_BU`, `SYSTEM_APP_USER` from `dev_tools.db.fixed_data`
- Connects via SQLAlchemy `create_engine(database_url)`
- Only runs if `verify_schema()` passed (guard: `if not missing:`) — if tables don't
  exist, bootstrap would fail with "relation does not exist"
- Executes 3 idempotent INSERTs in FK order (see `_shared_context.md` for exact SQL)

**Call site:** Insert between the "Step 5: Verify schema" block (~line 356) and the
"Step 6: Generate agent-context.env" block (~line 364). Guard behind `if not missing:`.
Verify `total_steps` current value before incrementing (plan assumes 5, confirm by
reading the variable definition at the top of `setup_database()`).

**Key details:**
- Values come from `fixed_data.py` constants, not hardcoded — use dict field access
- `created_at`/`updated_at` are mandatory in raw SQL (Python-side `default=` only)
- `is_active`/`version` safe to omit (have `server_default`)
- `app_user_tenant_role` is NOT bootstrapped — not needed for FK targets

### Verification
```sql
SELECT id FROM tenant WHERE id = 'tenant_sys_001';  -- returns 1 row
```
Run `linkedout setup` twice — no errors, no duplicate rows.

## Task 1b: Fix `./setup --auto`

**File:** `setup` (repo root), line 285

The one-shot eval chain appends `source $HOME/.local/bin/env 2>/dev/null` at the end.
After `curl | sh` installs uv, the env file may not exist yet. The `source` fails, the
entire `eval` exits non-zero, and the script reports "Auto-install failed".

**Fix:** Append `|| true` to the source line:
```bash
one_shot="${one_shot}source \$HOME/.local/bin/env 2>/dev/null || true"
```

### Verification
`./setup --auto` exits 0 when deps install but `~/.local/bin/env` is missing.

## Completion Criteria
- [ ] `bootstrap_system_records()` function exists and is called from `setup_database()`
- [ ] Bootstrap guarded behind schema verification success
- [ ] `./setup --auto` source line has `|| true`
- [ ] No lint errors in modified files
