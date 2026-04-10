# Sub-Phase 6: CLI Surface Refactor

**Phase:** 6 — Code Cleanup for OSS
**Plan task:** 6E (CLI Surface Refactor)
**Dependencies:** sp5 (small cleanups done, sp2-sp4 removals done — import tree is clean)
**Blocks:** sp9
**Can run in parallel with:** sp7, sp8
**Complexity:** Large

## Objective
Replace the `rcv2` CLI with the flat `linkedout` namespace per `docs/decision/cli-surface.md` (Phase 0A). Move implementation files from `dev_tools/` to `linkedout/commands/`. Create 13 user-facing commands + 1 internal command. Delete legacy entry points.

## Context
- Read shared context: `docs/execution/phase-06/_shared_context.md`
- Read plan (6E section): `docs/plan/phase-06-code-cleanup.md`
- **Read thoroughly:** `docs/decision/cli-surface.md` — authoritative contract for command names, flags, help text
- Read logging decision: `docs/decision/logging-observability-strategy.md` — operation result pattern
- Read data directory decision: `docs/decision/2026-04-07-data-directory-convention.md`
- Read existing CLI: `backend/src/dev_tools/cli.py`
- Read existing implementations:
  - `backend/src/dev_tools/load_linkedin_csv.py`
  - `backend/src/dev_tools/load_gmail_contacts.py`
  - `backend/src/dev_tools/compute_affinity.py`
  - `backend/src/dev_tools/generate_embeddings.py`
  - `backend/src/dev_tools/db/reset_db.py`

## Deliverables

### 1. Create Command Directory

Create `backend/src/linkedout/commands/` with `__init__.py`.

### 2. Move Implementation Files

Move (not copy) implementation logic from `dev_tools/` into `linkedout/commands/`:

| New File | Source | Notes |
|----------|--------|-------|
| `linkedout/commands/import_connections.py` | `dev_tools/load_linkedin_csv.py` | Add `--format`, `--dry-run` flags |
| `linkedout/commands/import_contacts.py` | `dev_tools/load_gmail_contacts.py` | Add `--format`, `--dry-run` flags |
| `linkedout/commands/compute_affinity.py` | `dev_tools/compute_affinity.py` | Add `--dry-run`, remove `--user-id` |
| `linkedout/commands/embed.py` | `dev_tools/generate_embeddings.py` | Add `--provider`, `--resume`, `--force` |
| `linkedout/commands/reset_db.py` | `dev_tools/db/reset_db.py` | Simplify to default truncate + `--full` |

For each moved file:
- Convert to a Click command (if not already)
- Update internal imports to use new module paths
- Ensure the core logic still works (don't rewrite business logic, just rewire the CLI wrapper)

### 3. Create New Command Files

| New File | Type | Notes |
|----------|------|-------|
| `linkedout/commands/start_backend.py` | New impl | Simple `uvicorn main:app` with `--port`, `--host`, `--background`. Must detect existing process on port, kill it, then start fresh. |
| `linkedout/commands/download_seed.py` | Stub | Print: "Not yet implemented — coming in Phase 7" |
| `linkedout/commands/import_seed.py` | Stub | Print: "Not yet implemented — coming in Phase 7" |
| `linkedout/commands/diagnostics.py` | Stub | Print: "Not yet implemented — coming in Phase 3" |
| `linkedout/commands/status.py` | Stub (basic) | Basic DB connectivity check. Full impl Phase 3. |
| `linkedout/commands/version.py` | New impl | Read VERSION file, print version + ASCII logo |
| `linkedout/commands/config.py` | Stub | `config path` prints config file location. Full impl Phase 2. |
| `linkedout/commands/report_issue.py` | Stub | Print: "Not yet implemented — coming in Phase 3" |
| `linkedout/commands/migrate.py` | New impl | Alembic wrapper, `--dry-run` support. Internal-only (hidden from main help). |

### 4. Create Main CLI Entry Point: `backend/src/linkedout/cli.py` (NEW)

Create a Click group with category-grouped help text matching `docs/decision/cli-surface.md`:

```
Usage: linkedout [OPTIONS] COMMAND [ARGS]...

  LinkedOut — your professional network, locally.

Data Import:
  import-connections  Import LinkedIn connections from CSV export
  import-contacts     Import Google contacts from CSV/vCard
  download-seed       Download demo seed dataset
  import-seed         Import seed dataset into local DB

Processing:
  compute-affinity    Compute relationship affinity scores
  embed               Generate embeddings for profile search

Server:
  start-backend       Start the LinkedOut API server

Diagnostics:
  diagnostics         Check system health and configuration
  status              Show current system status
  config              View or modify configuration
  report-issue        Generate a diagnostic bundle for bug reports

Meta:
  version             Show version information
  migrate             Run database migrations (internal)
```

Register all 14 commands on the group.

### 5. Create CLI Helpers: `backend/src/linkedout/cli_helpers.py` (NEW)

Shared utilities:
- `OperationResult` pattern (Progress → Summary → Gaps → Next steps → Report path) per `docs/decision/logging-observability-strategy.md`
- Category-grouped help text formatter (custom Click `HelpFormatter` or manual formatting)
- `--dry-run` decorator/mixin for write commands

### 6. Update `backend/pyproject.toml`

Add new entry point:
```toml
[project.scripts]
linkedout = "linkedout.cli:cli"
```

Remove ALL legacy entry points:
- `rcv2` — replaced by `linkedout`
- `reset-db`, `seed-db`, `verify-seed` — replaced by `linkedout reset-db`, etc.
- `pm` — retired (Langfuse-specific)
- `dev`, `be`, `fe`, `fe-setup`, `run-all-agents` — retired

### 7. Delete Legacy CLI Files

After moving implementations:
- Delete `backend/src/dev_tools/cli.py` (the old entry point)
- Delete any `dev_tools/` files whose logic was fully moved to `linkedout/commands/`
- Keep `dev_tools/` files that are still referenced by other code (e.g., `dev_tools/db/fixed_data.py` if used elsewhere)
- Evaluate: if `dev_tools/` is empty or only has files referenced by the new commands, consider whether to keep or remove the directory

### 8. Update Remaining `dev_tools` Imports

Any code outside `dev_tools/` that imports from `dev_tools` needs updating:
```bash
grep -rn "from dev_tools" backend/src/ --include="*.py" | grep -v "dev_tools/"
grep -rn "import dev_tools" backend/src/ --include="*.py" | grep -v "dev_tools/"
```

Common case: `dev_tools.db.fixed_data.SYSTEM_USER_ID` — if used by the new commands, update the import path or move `fixed_data.py` to a shared location.

## Verification
1. `cd backend && uv pip install -e . && linkedout --help` shows category-grouped help with all 13 user-facing commands
2. `linkedout version` prints version info
3. `linkedout config path` prints config file location
4. `linkedout import-connections --help` shows expected flags including `--dry-run`
5. `linkedout migrate --help` works (internal command)
6. Stub commands print "Not yet implemented" message with phase reference
7. `grep -rn "rcv2" backend/ --include="*.toml" --include="*.py"` returns zero matches
8. `cd backend && uv run ruff check src/linkedout/cli.py src/linkedout/commands/` clean
9. Legacy entry points removed from `pyproject.toml`
10. `cd backend && uv run python -c "from linkedout.cli import cli; print('CLI imports OK')"` succeeds

## Notes
- This is the largest sub-phase in Phase 6. Take time to read the existing implementations before moving them.
- The `docs/decision/cli-surface.md` is the authoritative spec. Match its command names, flag names, and help text exactly.
- `start-backend` must handle port conflicts: detect existing process, kill it, start fresh. No "address already in use" errors.
- Stub commands should use `click.echo("Not yet implemented — coming in Phase N")` and `raise SystemExit(0)`.
- `--dry-run` on write commands should preview what would happen without making changes.
- Keep `dev_tools/db/fixed_data.py` accessible — it contains `SYSTEM_USER_ID` and other fixed data used throughout the codebase.
