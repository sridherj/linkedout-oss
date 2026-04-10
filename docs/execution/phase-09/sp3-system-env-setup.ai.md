# Sub-Phase 3: System & Environment Setup

**Phase:** 9 — AI-Native Setup Flow
**Plan tasks:** 9C (Sudo Setup Script), 9D (Database Setup), 9E (Python Environment Setup)
**Dependencies:** sp2 (logging infrastructure + prerequisites detection)
**Blocks:** sp4
**Can run in parallel with:** —

## Objective
Create the sudo setup script for system-level dependencies, the user-space database setup module, and the Python environment setup module. These three are grouped because they form the "get the system ready" stage — the sudo script installs system packages, then database and Python env setup run in user-space using those packages.

## Context
- Read shared context: `docs/execution/phase-09/_shared_context.md`
- Read plan (9C + 9D + 9E sections): `docs/plan/phase-09-setup-flow.md`
- Read UX design doc: `docs/design/setup-flow-ux.md` (use exact wording)
- Read config design: `docs/decision/env-config-design.md`
- Read data directory convention: `docs/decision/2026-04-07-data-directory-convention.md`

## Deliverables

### 1. `scripts/system-setup.sh` (NEW)

Minimal, auditable shell script that does ONLY things requiring sudo. Users can read it before running.

**Design principles:**
- **Auditable:** Every action has a comment explaining what and why
- **Idempotent:** Safe to re-run. Uses `CREATE IF NOT EXISTS`, `createuser` with error suppression
- **Minimal:** Only 6 operations require sudo (package install, service start, user/db/extension creation)
- **Detectable:** Auto-detects platform or accepts `--platform` flag

**Header block:**
```bash
#!/usr/bin/env bash
# LinkedOut OSS — System Setup (requires sudo)
# This script installs system-level dependencies.
# Read it before running: cat scripts/system-setup.sh
#
# What this script does:
#   1. Installs postgresql + postgresql-contrib (for pg_trgm)
#   2. Installs postgresql-XX-pgvector (version-matched)
#   3. Ensures PostgreSQL service is running
#   4. Creates the 'linkedout' database user
#   5. Creates the 'linkedout' database
#   6. Installs SQL extensions (vector, pg_trgm) as superuser
#
# What this script does NOT do:
#   - Install Python (user should have Python 3.11+ already)
#   - Create venvs or install pip packages
#   - Write any config files
#   - Touch ~/linkedout-data/
```

**Platform-specific logic:**
- Debian/Ubuntu: `apt install postgresql postgresql-contrib postgresql-XX-pgvector`
- Arch: `pacman -S postgresql` + AUR `pgvector`
- Fedora/RPM: `dnf install postgresql-server postgresql-contrib pgvector_XX`
- macOS: `brew install postgresql@16 pgvector`
- WSL: Same as Debian/Ubuntu

**PostgreSQL version matching:** Detect installed PostgreSQL major version, install matching pgvector package.

**Database setup:**
```bash
sudo -u postgres createuser --no-superuser --createdb --no-createrole linkedout 2>/dev/null || true
sudo -u postgres createdb --owner=linkedout linkedout 2>/dev/null || true
sudo -u postgres psql -d linkedout -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u postgres psql -d linkedout -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

**Exit codes:** 0 = success, 1 = package install failed, 2 = PostgreSQL won't start, 3 = DB/extension creation failed.

### 2. `backend/src/linkedout/setup/database.py` (NEW)

Database configuration and setup — all user-space, no sudo.

**Implementation:**

1. **Password generation:** `secrets.token_urlsafe(24)` — 32-char alphanumeric.

2. **Set PostgreSQL password:**
   ```sql
   ALTER USER linkedout WITH PASSWORD 'generated_password';
   ```
   Execute via `psql` subprocess or direct psycopg2 connection.

3. **Write config.yaml:** Generate `~/linkedout-data/config/config.yaml` with `database_url` containing the generated password. Use template from `docs/decision/env-config-design.md`.

4. **Run Alembic migrations:** Wrap `alembic upgrade head` using the newly written `DATABASE_URL`.

5. **Verify schema:** Check key tables exist: `crawled_profile`, `company`, `connection`, `experience`, `education`, `profile_skill`, `role_alias`, `company_alias`, `funding_round`.

6. **Generate agent-context.env:**
   ```env
   DATABASE_URL=postgresql://linkedout:GENERATED@localhost:5432/linkedout
   LINKEDOUT_TENANT_ID=system
   LINKEDOUT_BU_ID=default
   LINKEDOUT_USER_ID=system
   ```

**Key functions:**
- `generate_password() -> str`
- `set_db_password(password: str)`
- `write_config_yaml(database_url: str, data_dir: Path)`
- `run_migrations(database_url: str) -> MigrationReport`
- `verify_schema(database_url: str) -> list[str]` — returns list of missing tables
- `generate_agent_context_env(database_url: str, data_dir: Path)`
- `setup_database(data_dir: Path) -> OperationReport` — full orchestration

**Idempotency:**
- Skip password generation if `config.yaml` already has a `database_url`
- Always run migrations (catches new migrations after upgrade)
- Always regenerate `agent-context.env` (ensures consistency)

**Integration:**
- Uses Phase 2 `LinkedOutSettings` for config file path resolution
- Uses Phase 2 directory layout (creates `~/linkedout-data/config/` if not exists)
- Uses Phase 3 `get_logger(__name__, component="setup", operation="db_setup")`
- Uses sp2 `get_setup_logger("database")` for step-level logging

### 3. `backend/src/linkedout/setup/python_env.py` (NEW)

Virtual environment creation and package installation.

**Implementation:**

1. **Create venv:** `python3 -m venv .venv` in repo root.

2. **Activate and install:**
   ```bash
   .venv/bin/pip install uv
   .venv/bin/uv pip install -r backend/requirements.txt
   .venv/bin/uv pip install -e backend/
   ```

3. **Verify CLI entry point:** `.venv/bin/linkedout --help` returns help text.

4. **Optional model pre-download:** If embedding provider is `local`, trigger model download of nomic-embed-text-v1.5 (~275MB) with progress display.

**Key functions:**
- `create_venv(repo_root: Path) -> bool` — returns True if created, False if already exists
- `install_dependencies(repo_root: Path) -> OperationReport`
- `verify_cli(repo_root: Path) -> bool`
- `pre_download_model(provider: str) -> bool` — download if local provider
- `setup_python_env(repo_root: Path, embedding_provider: str | None = None) -> OperationReport`

**Idempotency:**
- Skip venv creation if `.venv/` exists and is valid (check `.venv/bin/python3` exists and runs)
- Always run `uv pip install -r` (catches new dependencies after upgrade)

### 4. Unit Tests

**`backend/tests/linkedout/setup/test_database.py`** (NEW)
- `generate_password()` returns 32+ char string
- `generate_password()` produces different values each call
- `write_config_yaml()` creates valid YAML with `database_url` key
- `generate_agent_context_env()` creates file with `DATABASE_URL`, `LINKEDOUT_TENANT_ID`, etc.
- Config.yaml has correct permissions (not world-readable)
- Skips password gen when config.yaml already exists with `database_url`

**`backend/tests/linkedout/setup/test_python_env.py`** (NEW)
- `create_venv()` creates `.venv/` directory with `bin/python3`
- `create_venv()` returns False when `.venv/` already exists
- `install_dependencies()` runs without error (mock subprocess)
- `verify_cli()` returns True when linkedout command exists (mock)

## Verification
1. `bash scripts/system-setup.sh` completes without errors on the target OS
2. `psql -U linkedout -d linkedout -c "SELECT 1"` succeeds
3. `psql -U linkedout -d linkedout -c "SELECT * FROM pg_extension WHERE extname = 'vector'"` returns a row
4. `python -c "from linkedout.setup.database import setup_database"` imports without error
5. `python -c "from linkedout.setup.python_env import setup_python_env"` imports without error
6. `pytest backend/tests/linkedout/setup/test_database.py -v` passes
7. `pytest backend/tests/linkedout/setup/test_python_env.py -v` passes

## Notes
- `scripts/system-setup.sh` is pure bash — no Python dependency. It must work before Python env is set up.
- The sudo script targets Debian/Ubuntu primarily. macOS support via Homebrew. Arch/Fedora are best-effort.
- Database setup uses `secrets` module — never `random` for password generation.
- The venv is in the repo root (`.venv/`), not in `~/linkedout-data/`.
- Use `uv` for fast package installation, but install `uv` via pip first (bootstrapping).
