# /linkedout-dev — Engineering Principles

LinkedOut's engineering standards for contributors and AI agents. Reference this
skill when writing code, reviewing PRs, or building new features.

Every function, command, and pipeline in LinkedOut follows these principles.

---

## 1. Zero Silent Failures

Every operation must succeed completely or fail loudly with actionable diagnostics.
No step in any flow may fail silently.

**Why:** A silent failure is a time bomb. Users lose trust when they discover stale
data hours later. AI agents can't self-correct if they don't know something broke.

**How:**

- Every error includes three things: what failed, why it failed, what to do about it.
- Use exceptions with context, not return codes that callers might ignore.
- Log the failure immediately — don't aggregate errors and report them later.

```python
# WRONG — silent failure
try:
    profile = enrich_profile(url)
except Exception:
    pass  # move on to next profile

# RIGHT — loud failure with actionable context
try:
    profile = enrich_profile(url)
except EnrichmentError as e:
    logger.error(
        f"Failed to enrich {url}: {e.reason}. "
        f"Fix: {e.suggested_action}"
    )
    failures.append(FailureRecord(url=url, reason=str(e)))
```

**Reference:** `docs/decision/logging-observability-strategy.md` Section 12

---

## 2. Quantified Readiness (Not Boolean)

"Done" is never yes/no — it's precise counts. Every major operation produces a
readiness report with exact numbers.

**Why:** "Embeddings are done" is useless. "3,847/4,012 profiles have embeddings,
156 companies missing aliases" tells you exactly where you stand and what to fix.

**How:**

- Every operation that touches multiple records reports: total, succeeded, skipped, failed.
- Coverage gaps are explicit — name the gap type and count.
- Reports persist to `~/linkedout-data/reports/` as JSON for programmatic access.

```json
{
  "operation": "import-csv",
  "timestamp": "2026-04-07T14:23:05Z",
  "duration_ms": 4521,
  "counts": {
    "total": 3870,
    "succeeded": 3847,
    "skipped": 23,
    "failed": 0
  },
  "coverage_gaps": [
    {
      "type": "missing_company",
      "count": 156,
      "detail": "156 connections work at companies not in the database"
    },
    {
      "type": "missing_embedding",
      "count": 165,
      "detail": "165 profiles have no embedding vector"
    }
  ],
  "next_steps": [
    "Run `linkedout compute-affinity` to calculate affinity scores",
    "Run `linkedout embed` to generate embeddings for 165 profiles"
  ]
}
```

**Reference:** `docs/decision/logging-observability-strategy.md` Section 11

---

## 3. Operation Result Pattern

Every CLI command that modifies data follows this output contract:

```
Progress → Summary → Failures (with reasons) → Next steps → Report path
```

Commands never exit silently with just "Done".

**Why:** The user (or the AI agent invoking the command) needs to know what happened,
what's left, and what to do next — in a predictable, parseable format.

**How:**

Use the `OperationResult` class (built in Phase 3) for every CLI command.
Every command produces output in this exact pattern:

```
$ linkedout import-connections ~/Downloads/connections.csv

Loading connections from connections.csv...
  [============================] 3870/3870 profiles

Results:
  Imported:  3,847 new connections
  Skipped:   23 (already in database)
  Failed:    0

Coverage:
  Companies matched:  3,691 / 3,847 (95.9%)
  Missing companies:  156 (will resolve on next seed update)

Next steps:
  → Run `linkedout compute-affinity` to calculate affinity scores
  → Run `linkedout embed` to generate embeddings

Report saved: ~/linkedout-data/reports/import-csv-20260407-142305.json
```

**Reference:** `docs/decision/cli-surface.md` "Operation Result Pattern" section

---

## 4. Idempotency & Auto-Repair

Every operation must be safe to re-run. Re-running a step should fix incomplete
state, not corrupt it.

**Why:** Users interrupt operations, networks drop, machines restart. An operation
that corrupts data on re-run is a critical bug. An operation that detects and
repairs gaps on re-run is a feature.

**How:**

- Detect gap → report gap → offer to fix → repair → report results.
- Use upserts (INSERT ON CONFLICT UPDATE) instead of blind inserts.
- Track progress with checkpoints so interrupted operations resume, not restart.
- Every write command supports `--dry-run` to preview changes without committing.

```python
# WRONG — crashes on re-run
def import_connections(csv_path):
    for row in read_csv(csv_path):
        db.insert(row)  # fails on duplicate

# RIGHT — idempotent, resumable
def import_connections(csv_path, dry_run=False):
    existing = db.get_existing_urls()
    for row in read_csv(csv_path):
        if row.url in existing:
            skipped.append(row)
            continue
        if not dry_run:
            db.upsert(row)
        imported.append(row)
```

**Reference:** `docs/decision/cli-surface.md` (--dry-run requirement)

---

## 5. Structured Logging

Use loguru via the project's `get_logger()` wrapper. Every log entry binds
structured context fields for filtering and correlation.

**Why:** When something breaks in a batch of 4,000 profiles, you need to filter
logs by component + operation + correlation ID to find the needle in the haystack.

**How:**

- Import: `from shared.utilities.logger import get_logger`
- Create: `logger = get_logger(__name__, component="cli", operation="import_csv")`
- Every log entry automatically binds: `component`, `operation`, `correlation_id`
- Human-readable log format for console and files (structured data goes to reports/metrics, not logs)
- Per-component log files in `~/linkedout-data/logs/`

### Required fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `component` | str | Subsystem identifier | `backend`, `cli`, `extension`, `skill`, `setup` |
| `operation` | str | What's happening | `import_csv`, `enrich_profile`, `compute_affinity` |
| `correlation_id` | str | Request/session trace ID | `req_abc123`, `cli_import_20260407_1423` |

### Log format

Console output is always human-readable:
```
14:23:05 I cli.import Imported 3847 connections from CSV (23 skipped, 0 failed)
```

File logs include full context:
```
2026-04-07 14:23:05.123 | INFO | cli.import:run_import:45 | Imported 3847 connections
```

### Log file layout

```
~/linkedout-data/logs/
├── backend.log          # Backend API server logs
├── cli.log              # All CLI command execution logs
├── setup.log            # Setup flow logs
├── enrichment.log       # Enrichment pipeline logs
├── import.log           # CSV/contact import operations
├── queries.log          # Search queries and results summaries
└── archive/             # Rotated log files (gzip, 50MB rotation, 30-day retention)
```

**Reference:** `docs/decision/logging-observability-strategy.md`

---

## 6. CLI Design

The `linkedout` CLI uses a flat namespace with short, verb-first, hyphen-separated
command names. No subgroups.

**Why:** Users interact with ~13 commands total. Subgroups add cognitive overhead
without organizational benefit at this scale. Skills invoke these commands as
building blocks — predictable, deterministic operations.

**How:**

- **Flat namespace:** `linkedout import-connections`, NOT `linkedout db import-connections`
- **`--dry-run`** on every write command — users and skills preview before committing
- **`--json`** where skills need machine-readable output (e.g., `status`, `diagnostics`)
- **Auto-detection** over explicit flags — `import-connections` auto-detects CSV format
- **Verb-first naming:** `import-connections`, `compute-affinity`, `download-seed`

### Complete command list

```
Import:       import-connections, import-contacts, import-seed
Seed Data:    download-seed
Intelligence: compute-affinity, embed
System:       status, diagnostics, version, config, report-issue
Server:       start-backend
Database:     reset-db
```

**Reference:** `docs/decision/cli-surface.md`

---

## 7. Configuration

Three-layer hierarchy where env vars always win:

```
Environment variable          # LINKEDOUT_EMBEDDING_PROVIDER=local
  ↓ overrides
~/linkedout-data/config/config.yaml      # embedding_provider: openai
  ↓ overrides
~/linkedout-data/config/secrets.yaml     # openai_api_key: sk-...
  ↓ overrides
Code defaults                            # embedding_provider = "openai"
```

**Why:** YAML is human-readable and commentable. Env vars provide overrides for CI
and automation. Separate secrets file prevents accidental API key leaks when sharing
config.

**How:**

- `LINKEDOUT_` prefix for LinkedOut-specific vars
- Industry-standard names kept as-is: `DATABASE_URL`, `OPENAI_API_KEY`
- All data under `~/linkedout-data/` (configurable via `LINKEDOUT_DATA_DIR`)
- `secrets.yaml` is `chmod 600` — API keys only
- pydantic-settings validates at startup with clear, actionable error messages

### Key directories

```
~/linkedout-data/
├── config/          # config.yaml, secrets.yaml, agent-context.env
├── logs/            # Application logs (per-component)
├── reports/         # Operation reports (JSON)
├── metrics/         # Usage metrics (JSONL)
├── seed/            # Downloaded seed data
├── crawled/         # Extension-crawled profiles
└── state/           # Embedding progress, sync state
```

**Reference:** `docs/decision/env-config-design.md`

---

## 8. Testing

Tests must pass without external API keys. The test suite validates correctness
without requiring network access or paid services.

**Why:** Contributors shouldn't need an OpenAI API key to run tests. CI shouldn't
cost money per run. Tests that depend on external services are flaky by definition.

**How:**

- **Mock LLM/API calls** in unit tests — never hit real APIs
- **Integration tests use real PostgreSQL** — a local pgvector Docker image in CI provides the real database engine, not SQLite stubs
- **Three test tiers:**
  1. **Static analysis** — ruff (lint) + pyright (type check). Fast, runs on every commit.
  2. **Integration tests** — pytest against real PostgreSQL. Runs on every PR.
  3. **Installation tests** — end-to-end install + smoke test. Runs nightly.

```bash
# Static analysis (fast, no dependencies)
ruff check backend/src/
pyright backend/src/

# Integration tests (requires local PostgreSQL with pgvector)
pytest backend/tests/

# Run a specific test file
pytest backend/tests/unit/test_import.py -v
```

- `nomic-embed-text-v1.5` is the default local embedding model for tests that need embeddings
- Tests that need a database use pytest fixtures that create/tear down test schemas

**Reference:** `docs/decision/logging-observability-strategy.md` (testing tiers)

---

## Quick Reference

| Principle | One-liner |
|-----------|-----------|
| Zero Silent Failures | Every error: what failed, why, what to do |
| Quantified Readiness | Precise counts, not booleans |
| Operation Result Pattern | Progress → Summary → Failures → Next steps → Report path |
| Idempotency | Safe to re-run, repairs gaps, supports --dry-run |
| Structured Logging | loguru + get_logger() with component/operation/correlation_id |
| CLI Design | Flat namespace, verb-first, --dry-run on writes |
| Configuration | env vars > config.yaml > secrets.yaml > defaults |
| Testing | No API keys needed, real PostgreSQL in CI, three tiers |
