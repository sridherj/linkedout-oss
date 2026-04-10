# Phase 4c: CLI Commands — cli_db_manager() Pattern

## Goal

Replace all `db_session_manager.get_session()` calls in CLI commands and dev_tools scripts with the `cli_db_manager()` pattern. Each entry point creates its own manager at the top, then uses it throughout.

## Dependencies

**Requires Phase 4a complete** — `cli_db_manager()` and the new `DbSessionManager(engine)` constructor must exist.

Can run in parallel with Phase 4b.

## Pattern

Every file follows the same mechanical transformation:

**Before:**
```python
from shared.infra.db.db_session_manager import db_session_manager, DbSessionType
...
with db_session_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
    ...
```

**After:**
```python
from shared.infra.db.cli_db import cli_db_manager
from shared.infra.db.db_session_manager import DbSessionType
...
db_manager = cli_db_manager()
with db_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
    ...
```

**Key rule:** Create `db_manager = cli_db_manager()` once at the entry point of the function/script, then reuse the same `db_manager` for all `get_session()` calls within that function. Do NOT create a new manager per `get_session()` call.

For files with multiple functions that each serve as entry points, each function creates its own `db_manager`.

## Files to Change

### Registered CLI commands (5 files)

#### 1. `src/linkedout/commands/import_seed.py`
- Import: Replace `from shared.infra.db.db_session_manager import db_session_manager, DbSessionType` with `from shared.infra.db.cli_db import cli_db_manager` and `from shared.infra.db.db_session_manager import DbSessionType`
- Line 245: `db_session_manager.get_session(...)` → `db_manager.get_session(...)`
- Add `db_manager = cli_db_manager()` at the top of the CLI command function (find the `@click.command()` decorated function)

#### 2. `src/linkedout/commands/import_connections.py`
- Lines 215, 227: Replace `db_session_manager.get_session()` calls
- Add `db_manager = cli_db_manager()` at the top of the CLI command function
- Update import

#### 3. `src/linkedout/commands/import_contacts.py`
- Lines 487, 496: Replace `db_session_manager.get_session()` calls
- Add `db_manager = cli_db_manager()` at the top of the CLI command function
- Update import

#### 4. `src/linkedout/commands/embed.py`
- Lines 135, 158, 256, 267: Replace 4 `db_session_manager.get_session()` calls
- This file has multiple functions. Add `db_manager = cli_db_manager()` at the top of each entry-point function that uses sessions
- Update import

#### 5. `src/linkedout/commands/compute_affinity.py`
- Lines 29, 43: Replace `db_session_manager.get_session()` calls
- Add `db_manager = cli_db_manager()` at the top of the CLI command function
- Update import

### Standalone dev_tools scripts (~15 files)

Same mechanical pattern for each:

#### 6. `src/dev_tools/db/seed.py`
- Line 33: Replace `db_session_manager.get_session()` call

#### 7. `src/dev_tools/db/load_fixtures.py`
- Line 87: Replace `db_session_manager.get_session()` call

#### 8. `src/dev_tools/db/validate_orm.py`
- This file references `db_session_manager` in error messages/strings (lines 277, 290) but doesn't call `get_session()` — **no functional change needed**, only update the string references if they mention "db_session_manager" as a module name (they do — these are informational strings about where entity registration happens, so keep them accurate).

#### 9. `src/dev_tools/db/verify_seed.py`
- Line 32: Replace `db_session_manager.get_session()` call

#### 10. `src/dev_tools/seed_companies.py`
- Lines 111, 245, 308: Replace 3 `db_session_manager.get_session()` calls

#### 11. `src/dev_tools/reconcile_stubs.py`
- Lines 243, 262: Replace 2 `db_session_manager.get_session()` calls

#### 12. `src/dev_tools/classify_roles.py`
- Line 104: Replace `db_session_manager.get_session()` call

#### 13. `src/dev_tools/import_pdl_companies.py`
- Lines 106, 180: Replace 2 `db_session_manager.get_session()` calls

#### 14. `src/dev_tools/fix_none_names.py`
- Lines 30, 43: Replace 2 `db_session_manager.get_session()` calls

#### 15. `src/dev_tools/backfill_experience_dates.py`
- Line 29: Replace `db_session_manager.get_session()` call

#### 16. `src/dev_tools/backfill_seniority.py`
- Line 17: Replace `db_session_manager.get_session()` call

#### 17. `src/dev_tools/load_apify_profiles.py`
- Lines 438, 454: Replace 2 `db_session_manager.get_session()` calls

#### 18. `src/dev_tools/download_profile_pics.py`
- Lines 55, 139: Replace 2 `db_session_manager.get_session()` calls

#### 19. `src/dev_tools/enrich_companies.py`
- Lines 433, 485, 507, 522: Replace 4 `db_session_manager.get_session()` calls

#### 20. `src/dev_tools/seed_export.py`
- Line 267: Replace `db_session_manager.get_session()` call

### Other files

#### 21. `src/linkedout/version.py`
- Line 55: Replace `db_session_manager.get_session()` call
- This is inside a `try` block within a function — create `db_manager` inside the try block:
  ```python
  try:
      from shared.infra.db.cli_db import cli_db_manager
      from shared.infra.db.db_session_manager import DbSessionType
      db_manager = cli_db_manager()
      with db_manager.get_session(DbSessionType.READ) as session:
          ...
  ```

**Note:** `health_checks.py` and `diagnostics.py` are already handled in Phase 4a.

## Verification

After this phase, all CLI imports should work:

```bash
cd ./backend && uv run python -c "
# Verify all CLI command modules import cleanly
from linkedout.commands.import_seed import import_seed_command
from linkedout.commands.import_connections import import_connections
from linkedout.commands.embed import embed
from linkedout.commands.compute_affinity import compute_affinity
print('All CLI command modules import OK')
"
```

```bash
# Verify no remaining references to the old db_session_manager global in CLI/dev_tools
cd ./backend && grep -rn "db_session_manager\.get_session\|db_session_manager\.set_engine\|from.*import.*db_session_manager" src/linkedout/commands/ src/dev_tools/ src/linkedout/version.py --include="*.py" | grep -v "# " | head -20
```

**Expected:** No matches (all references to `db_session_manager` replaced with `cli_db_manager()`).

**Do NOT run the full test suite** — test fixtures still use `set_engine()` (fixed in Phase 4d).
