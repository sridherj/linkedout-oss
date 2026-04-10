# Sub-phase 2: Demo Download & Restore Commands

## Metadata

| Field | Value |
|-------|-------|
| Sub-phase | SP2 |
| Dependencies | SP1 (demo constants and config helpers) |
| Estimated effort | 2 sessions (~6 hours) |
| Branch | main |
| Plan reference | `docs/plan/2026-04-08-demo-seed-plan.md` — Sub-phase 2 |
| Spec reference | `backend/docs/specs/onboarding-experience.md` |

## Objective

Two new CLI commands exist: `linkedout download-demo` downloads the demo dump from GitHub Releases to `~/linkedout-data/cache/demo-seed.dump`, and `linkedout restore-demo` creates the `linkedout_demo` database and restores the dump into it. Both are idempotent.

## Context

This sub-phase creates the core demo data pipeline — downloading a pre-built pg_dump from GitHub Releases and restoring it into a local Postgres database. These commands are used both by the setup orchestrator (SP3) and directly by users.

### Key existing files (read these before implementing)

- `backend/src/linkedout/commands/download_seed.py` — Reference pattern for GitHub Release download with manifest, checksums, progress bar
- `backend/src/linkedout/setup/database.py` — Postgres connection patterns, `write_config_yaml`
- `backend/src/linkedout/commands/reset_db.py` — subprocess.run with psql pattern
- `backend/src/linkedout/cli.py` — Command registration
- `backend/src/linkedout/demo/__init__.py` — Demo constants (from SP1): `DEMO_DB_NAME`, `DEMO_CACHE_DIR`, `DEMO_DUMP_FILENAME`, `set_demo_mode`, `get_demo_db_url`

## Tasks

### 1. Create download-demo command

Create `backend/src/linkedout/commands/download_demo.py`:

- Click command `download-demo` with `--force` and `--version` options
- Reuse patterns from `download_seed.py`: GitHub Release URL resolution, manifest fetching, checksum verification, progress bar download
- The demo dump is a separate GitHub Release asset (tag: `demo-v1` or similar) with its own manifest (`demo-manifest.json`) containing `{name, sha256, size_bytes}`
- Cache location: `~/linkedout-data/cache/demo-seed.dump` (not `seed/` — demo is separate from seed data)
- On success: print cache location and next step hint ("Run `linkedout restore-demo`")
- Constants: `DEMO_RELEASE_TAG = "demo-v1"`, `DEMO_REPO = "sridherj/linkedout-oss"` (same repo, different release tag)

### 2. Create demo database utilities

Create `backend/src/linkedout/demo/db_utils.py` with shared helpers:

- `create_demo_database(db_url: str) -> str` — creates `linkedout_demo`, returns its URL
- `drop_demo_database(db_url: str) -> bool` — drops `linkedout_demo` if it exists
- `restore_demo_dump(demo_db_url: str, dump_path: Path) -> bool` — runs pg_restore
- `get_demo_stats(demo_db_url: str) -> dict` — queries profile/company/connection counts
- `check_pg_restore() -> bool` — verifies `pg_restore` is available on the system

All functions use `subprocess.run` with `psql`/`pg_restore` — matching the pattern in `database.py` and `reset_db.py`.

### 3. Create restore-demo command

Create `backend/src/linkedout/commands/restore_demo.py`:

- Click command `restore-demo`
- Check that `~/linkedout-data/cache/demo-seed.dump` exists (error with helpful message if not: "Run `linkedout download-demo` first")
- Read current `database_url` from config to extract host/port/user/password
- Create database: handle "already exists" gracefully (`DROP DATABASE IF EXISTS linkedout_demo` then create)
- Enable pgvector: `CREATE EXTENSION IF NOT EXISTS vector` in the new DB
- Run `pg_restore --dbname=linkedout_demo --clean --if-exists --no-owner` on the dump
- Call `set_demo_mode(data_dir, enabled=True)` to update config
- Regenerate `agent-context.env` with the demo database URL
- Print success: profile count, company count, sample query suggestion
- Print the demo user profile explanation (founder/CTO composite)

### 4. Update prerequisites check

Update `backend/src/linkedout/setup/prerequisites.py`:

- Add `pg_restore` availability check alongside existing `psql` check
- `pg_restore` ships with the PostgreSQL client package (same as `psql`)
- If `psql` exists but `pg_restore` is missing, add to blockers list

### 5. Register commands in CLI

Register both commands in `backend/src/linkedout/cli.py` under a new `# --- Demo ---` section.

### 6. Write tests

- Unit: `test_download_demo.py` — mock HTTP, test cache hit/miss/force logic
- Integration: `test_restore_demo.py` — requires a running Postgres (skip in CI if unavailable). Test create/drop/restore cycle.

## Verification Checklist

- [ ] `linkedout download-demo` downloads a file to `~/linkedout-data/cache/demo-seed.dump` (or skips if cached and checksum matches)
- [ ] `linkedout download-demo --force` re-downloads even if cached
- [ ] `linkedout restore-demo` creates `linkedout_demo` DB if not exists, runs `pg_restore`
- [ ] `linkedout restore-demo` is idempotent (drop + recreate on repeat)
- [ ] After restore, `psql linkedout_demo -c "SELECT count(*) FROM crawled_profile"` returns expected count
- [ ] Config is updated to `demo_mode: true` and `database_url` points to `linkedout_demo`
- [ ] `agent-context.env` is regenerated with the demo database URL
- [ ] Both commands registered in `cli.py` and appear in `linkedout --help`
- [ ] All tests pass

## Design Notes

- **Naming:** `download-demo` and `restore-demo` follow the `verb-noun` pattern used by `download-seed`, `import-seed`, `compute-affinity`, `reset-db`.
- **Error paths:** `pg_restore` failure is retryable — `--clean --if-exists` flags mean partial restores can be re-run. `DROP DATABASE IF EXISTS` before create ensures a clean slate.
- **Security:** Demo database URL uses the same credentials as the main database. The dump file is downloaded over HTTPS from GitHub.
- **Flat CLI:** Considered `linkedout demo download` / `linkedout demo restore` as a subcommand group, but the existing CLI is flat. Flat commands with `demo` in the name are more discoverable and consistent.
