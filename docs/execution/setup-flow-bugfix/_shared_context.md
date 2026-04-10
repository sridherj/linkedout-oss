# Setup Flow Bugfix — Shared Context

## Problem Summary

Three integration test runs exposed 14 issues in the LinkedOut setup flow. 2 are already
fixed, 12 remain open. The issues cluster into 4 groups:

1. **Missing DB bootstrap** (root cause) — System tenant/BU/user records are never
   created after migrations, causing FK violations on `connection` and `enrichment_event`
   INSERTs. Every CSV import row errors, savepoint rollback undoes stub profiles, and
   0 profiles end up in the DB.
2. **Code bugs** — Missing timestamps in raw SQL, wrong CLI invocation pattern,
   double-counting in CSV import, hardcoded IDs instead of constants.
3. **Non-TTY incompatibility** — `input()`/`getpass()` calls block in Claude Code's
   non-interactive Bash tool (EOFError). Skill template sources `agent-context.env`
   before it exists.
4. **Spec gaps** — Bootstrap, degradation behavior, non-TTY handling, and implementation
   conventions are undocumented.

## Key Constraints

### Table Names
- Table is `bu`, NOT `business_unit` (`BuEntity.__tablename__ = 'bu'`)
- Table is `tenant`, `app_user`, `connection`, `crawled_profile`, `enrichment_event`

### Timestamp Requirements
- `created_at`/`updated_at` use Python-side `default=` (NOT `server_default`)
- Raw SQL INSERTs MUST include `NOW()` for both columns
- `is_active` and `version` have `server_default` — safe to omit

### fixed_data Imports
- Source of truth: `backend/src/dev_tools/db/fixed_data.py`
- Constants: `SYSTEM_TENANT`, `SYSTEM_BU`, `SYSTEM_APP_USER`, `SYSTEM_USER_ID`
- Values: `tenant_sys_001`, `bu_sys_001`, `usr_sys_001`
- Always import from `dev_tools.db.fixed_data`, never hardcode

### System Record IDs
```
SYSTEM_TENANT['id']    = 'tenant_sys_001'
SYSTEM_BU['id']        = 'bu_sys_001'
SYSTEM_APP_USER['id']  = 'usr_sys_001'
SYSTEM_USER_ID         = 'usr_sys_001'
```

### Bootstrap Insert Order (FK dependencies)
1. `tenant` first (no FK deps)
2. `bu` second (FK to `tenant.id`)
3. `app_user` third (no FK to tenant/BU directly)

### CLI Entry Point
- Use `["linkedout", ...]` not `[sys.executable, "-m", "linkedout.commands", ...]`
- Entry point installed by `pip install -e backend/`
- Exception: `skill_install.py` uses `sys.executable` to run a Python script (correct)
- Exception: `logging_integration.py` reads `sys.executable` for diagnostics (correct)

### EOFError Pattern
```python
try:
    choice = input("Prompt [y/N] ").strip().lower()
except (EOFError, KeyboardInterrupt):
    choice = ""  # default to safe/conservative choice
```

### Skill Template
- Source: `skills/linkedout-setup/SKILL.md.tmpl` (mustache vars)
- Output: `skills/claude-code/linkedout-setup/SKILL.md`
- Config path: `~/linkedout-data/config/secrets.yaml`
- NEVER source `agent-context.env` before setup — setup creates it

## Plan Source
`./docs/plan/2026-04-10-setup-flow-bugfix.md`

## DAG (Dependency Graph)

```
01-foundation-bootstrap
  |
  +---> 02c-fix-csv-double-counting
  |
  (all other 02x sub-phases are independent of 01 and each other)

02a-fix-timestamps ----+
02b-fix-sys-executable -+---> 04-spec-updates
02c-fix-csv-double-counting -+---> 05-tests
02d-fix-hardcoded-ids --+
03-skill-rewrite-nontty +
```

## Files Modified (Full List)

| File | Sub-phase |
|------|-----------|
| `backend/src/linkedout/setup/database.py` | 01 |
| `setup` (repo root) | 01 |
| `backend/src/linkedout/setup/user_profile.py` | 02a, 03 |
| `backend/src/linkedout/setup/csv_import.py` | 02b, 03 |
| `backend/src/linkedout/setup/contacts_import.py` | 02b, 03 |
| `backend/src/linkedout/setup/auto_repair.py` | 02b, 03 |
| `backend/src/linkedout/setup/readiness.py` | 02b |
| `backend/src/linkedout/setup/seed_data.py` | 02b, 03 |
| `backend/src/linkedout/setup/affinity.py` | 02b |
| `backend/src/linkedout/setup/embeddings.py` | 02b, 03 |
| `backend/src/linkedout/setup/enrichment.py` | 02d, 03 |
| `backend/src/linkedout/setup/api_keys.py` | 03 |
| `backend/src/linkedout/setup/skill_install.py` | 03 |
| `backend/src/linkedout/commands/import_connections.py` | 02c, 02d |
| `skills/linkedout-setup/SKILL.md.tmpl` | 03 |
| `skills/claude-code/linkedout-setup/SKILL.md` | 03 |
| `docs/specs/onboarding-experience.md` | 04 |
| `backend/tests/linkedout/setup/test_database.py` | 05 |
| `backend/tests/linkedout/commands/test_import_connections.py` | 05 |
| `backend/tests/linkedout/setup/test_user_profile.py` | 05 |
