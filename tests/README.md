# LinkedOut Test Suite

## Test Tiers

### Tier 1: Static Validation

- **What:** ruff lint + ruff format check + pyright type check
- **Trigger:** Every push, every PR
- **Cost:** Free (no DB, no API keys)
- **Run locally:**
  ```bash
  cd backend
  ruff check src/
  ruff format --check src/
  pyright src/
  ```

### Tier 2: Unit Tests (pytest, mocked DB)

- **What:** pytest with SQLite in-memory DB, mocked external calls
- **Trigger:** Every push, every PR
- **Cost:** Free (no real DB, no API keys)
- **Run locally:**
  ```bash
  cd backend
  LINKEDOUT_ENVIRONMENT=test pytest tests/
  ```
- **What it catches:** Logic errors in repositories, services, controllers, schemas, and utilities. Uses SQLite with JSONB/ARRAY compatibility shims.
- **Parallelism:** Uses `pytest-xdist` (`-n auto --dist=loadfile`)

### Tier 3: Integration Tests (real PostgreSQL)

- **What:** Full-stack tests against real PostgreSQL with Alembic migrations
- **Trigger:** Every push, every PR (CI provides PostgreSQL service)
- **Cost:** Free (local PostgreSQL only, all external APIs mocked)
- **Run locally:**
  ```bash
  cd backend
  LINKEDOUT_ENVIRONMENT=test pytest tests/ -m integration
  ```
- **What it catches:** SQL dialect differences (SQLite vs PostgreSQL), migration issues, FK constraints, pgvector operations, real transaction behavior.
- **Requires:** PostgreSQL 16+ running locally with a test database

### Tier 4: Installation Tests

- **What:** Full setup flow validation (Phase 9R suite)
- **Trigger:** Nightly schedule + release branch pushes
- **Cost:** Free (mocked APIs, optional PostgreSQL for `@requires_postgres` tests)
- **Run locally:**
  ```bash
  pytest tests/installation/ -v --tb=long
  ```
- **What it catches:** Setup orchestrator bugs, prerequisite detection failures, idempotency regressions, permission issues, degraded-environment handling.
- **Location:** `tests/installation/`
- **Details:** See `tests/installation/README.md` for fixtures and conventions

### Tier 5: Skill Tests

- **What:** Cross-platform skill template engine and config tests
- **Trigger:** Every push, every PR (runs with Tier 2)
- **Cost:** Free (pure logic tests)
- **Run locally:**
  ```bash
  pytest tests/skills/ -v
  ```
- **What it catches:** Template rendering bugs, frontmatter parsing errors, host config loading issues (Claude Code, Codex, Copilot).
- **Location:** `tests/skills/`

### Tier 6: LLM Eval (Optional)

- **What:** Evaluate search/query quality with real LLM calls
- **Trigger:** Manual dispatch only (`pytest -m eval`)
- **Cost:** Requires OpenAI API key ($)
- **Run locally:**
  ```bash
  cd backend
  pytest tests/eval/ -m eval -v
  ```
- **Note:** Not a release gate — informational quality tracking only

## Test Markers

| Marker | Purpose |
|--------|---------|
| `unit` | Unit tests (default, no extra infra needed) |
| `integration` | Requires real PostgreSQL |
| `live_llm` | Makes live LLM provider calls (needs API keys) |
| `live_langfuse` | Requires Langfuse API access |
| `live_services` | Calls external services (Apify, etc.) |
| `eval` | Search quality evaluation |
| `slow` | Slow tests (skip with `-m "not slow"`) |
| `requires_postgres` | Needs PostgreSQL (installation tests) |

## Default Test Run

By default, `pytest` in `backend/` excludes expensive markers:

```
-m "not live_llm and not live_langfuse and not live_services and not integration and not eval"
```

This runs Tier 2 (unit) tests only. Use `-m integration` to include Tier 3.

## CI Workflow Summary

| Tier | CI Job | Trigger | Workflow |
|------|--------|---------|----------|
| 1 (Static) | `lint` + `typecheck` | push + PR | `.github/workflows/ci.yml` |
| 2 (Unit) | `test` | push + PR | `.github/workflows/ci.yml` |
| 3 (Integration) | `integration` | push + PR | `.github/workflows/ci.yml` |
| 4 (Installation) | `installation-test` | nightly + release | `.github/workflows/ci.yml` |
| Extension | `extension-build` | release + manual | `.github/workflows/extension-build.yml` |

## Directory Layout

```
tests/
├── installation/         # Tier 4: Setup flow tests
│   ├── conftest.py       # Fixtures: temp_data_dir, test_db, mock_github_releases
│   ├── test_fresh_install.py
│   ├── test_idempotency.py
│   ├── test_partial_recovery.py
│   ├── test_permissions.py
│   ├── test_prerequisites.py
│   ├── test_degraded.py
│   └── README.md
└── skills/               # Tier 5: Skill engine tests
    ├── test_config.py
    ├── test_frontmatter.py
    └── test_template.py

backend/tests/
├── unit/                 # Tier 2: Mocked unit tests (~130 files)
├── integration/          # Tier 3: Real PostgreSQL tests (~45 files)
├── linkedout/            # Entity wiring tests (repos, services, controllers)
├── live_llm/             # Live LLM provider tests
├── live_services/        # External service tests
├── eval/                 # Search quality evaluation
├── common/               # Base class tests
├── shared/               # Shared utilities tests
├── utilities/            # LLM manager tests
├── dev_tools/            # CLI and tool tests
└── organization/         # Tenant/BU tests
```
