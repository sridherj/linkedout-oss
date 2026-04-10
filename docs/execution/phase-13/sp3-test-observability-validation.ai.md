# SP3: Test Suite & Observability Validation

**Phase:** 13 — Polish & Launch
**Sub-phase:** 3 of 6
**Dependencies:** None (can run in parallel with SP1 and SP2)
**Estimated effort:** ~2 hours
**Shared context:** `_shared_context.md`

---

## Scope

Validate that the three-tier test suite is properly organized with clear CI triggers, and that every subsystem produces the expected logging, metrics, and report artifacts per the observability decision doc. This is primarily a **validation task** — if gaps are found, fix inline or file issues.

**Tasks from phase plan:** 13D (test suite validation), 13E (observability validation)

**Agent references (final release audit):**
- `.claude/agents/crud-compliance-checker-agent.md` — Run compliance checks across ALL CRUD stacks before release. Generate a compliance report for each entity.
- `.claude/agents/review-ai-agent.md` — Audit AI agent implementations against their writeups. Catch any drift from Phases 2-12.
- `.claude/agents/integration-test-creator-agent.md` — Verify all entities have proper integration test coverage, fixtures, and seeding.

---

## Part 1: Three-Tier Test Suite Validation (13D)

### Required reading
- `.github/workflows/ci.yml` — Current CI workflow
- `tests/` directory structure — What tests exist
- `tests/installation/` — Phase 9R installation test suite
- `docs/decision/logging-observability-strategy.md` — Defines test tiers

### Create: tests/README.md

**File to create:** `tests/README.md`

Document all test tiers, how to run each locally, and what each tier catches.

#### Content structure:

```markdown
# LinkedOut Test Suite

## Test Tiers

### Tier 1: Static Validation
- **What:** ruff lint + ruff format check + pyright type check
- **Trigger:** Every push, every PR
- **Cost:** Free (no DB, no API keys)
- **Run locally:**
  - `ruff check backend/src/`
  - `ruff format --check backend/src/`
  - `pyright backend/src/`

### Tier 2: Integration Tests
- **What:** pytest with real PostgreSQL, mocked LLM/API calls
- **Trigger:** Every push, every PR
- **Cost:** Free (local DB only)
- **Run locally:**
  - Requires: PostgreSQL running with test database
  - `LINKEDOUT_ENVIRONMENT=test pytest backend/tests/`

### Tier 3: Installation Tests
- **What:** Full setup flow on real OS (Phase 9R suite)
- **Trigger:** Nightly schedule + release branch pushes
- **Cost:** Free (uses local nomic embeddings, no API keys)
- **Run locally:**
  - `bash tests/installation/test_fresh_install.sh`

### Tier 4: LLM Eval (Optional)
- **What:** Evaluate skill/query quality with real LLM calls
- **Trigger:** Manual dispatch only
- **Cost:** Requires OpenAI API key ($)
- **Note:** Not a release gate — informational quality tracking only
```

### Verify CI workflow configuration

Check `.github/workflows/ci.yml` and verify/update:

**Tier 1 (Static) — separate job:**
- [ ] `ruff check backend/src/` passes with zero warnings
- [ ] `ruff format --check backend/src/` passes
- [ ] `pyright backend/src/` passes with zero errors
- [ ] Triggers on every push and PR

**Tier 2 (Integration) — separate job:**
- [ ] pytest runs with a real PostgreSQL (`services: postgres` in GitHub Actions)
- [ ] All external API calls (OpenAI, Apify, Langfuse) are mocked — no API keys needed in CI
- [ ] Test database is created/destroyed per test session (fixture in `conftest.py`)
- [ ] Alembic migrations run cleanly against test DB
- [ ] Coverage report generated
- [ ] Uses `LINKEDOUT_ENVIRONMENT=test` and test-specific `DATABASE_URL`
- [ ] PostgreSQL service version is 16 or 17
- [ ] Triggers on every push and PR

**Extension tests (if applicable):**
- [ ] Extension Tier 1: `vitest run` or equivalent build-time checks
- [ ] Runs as separate job with Node.js setup

**CI timing:**
- [ ] Tier 1 + 2 combined finish in < 5 minutes

### Gap handling

For each validation item that fails:
- If it's a quick fix (< 15 min): fix inline
- If it's larger: create a TODO comment in the relevant file and note it in the sub-phase output

---

## Part 2: Observability Validation (13E)

### Required reading
- `docs/decision/logging-observability-strategy.md` — Authoritative source for all observability requirements
- `backend/src/shared/utilities/logger.py` — Logging setup
- `backend/src/shared/config/config.py` — Config singleton

### Validation Checklist

#### Logging infrastructure
- [ ] All backend modules use `get_logger(__name__)` from `shared.utilities.logger` (no raw `import logging`)
- [ ] Every log entry carries `component` and `operation` fields via loguru `bind()`
- [ ] Console output is human-readable (`HH:mm:ss LEVEL module message`)
- [ ] File logs go to `~/linkedout-data/logs/` (not `backend/logs/`)
- [ ] Per-component log files exist: `backend.log`, `cli.log`, `setup.log`, `enrichment.log`, `import.log`, `queries.log`
- [ ] Log rotation: 50MB per file, 30-day retention, gzip compression to `archive/`
- [ ] `LINKEDOUT_LOG_LEVEL` and `LOG_LEVEL_<MODULE>` overrides work

#### Correlation IDs
- [ ] Backend API: every request gets a `correlation_id` (nanoid, prefix `req_`)
- [ ] CLI: every command invocation gets a `correlation_id` (prefix `cli_`)
- [ ] Backend returns `X-Correlation-ID` response header

#### CLI operation result pattern

Verify EVERY CLI command follows this pattern:
1. Progress during execution
2. Summary on completion (succeeded/skipped/failed)
3. Failures listed with reasons (if any)
4. Report persisted to `~/linkedout-data/reports/`

Check each command by reading its implementation:

| Command | Progress | Summary | Failures | Report |
|---------|----------|---------|----------|--------|
| `import-connections` | [ ] | [ ] | [ ] | [ ] |
| `import-contacts` | [ ] | [ ] | [ ] | [ ] |
| `compute-affinity` | [ ] | [ ] | [ ] | [ ] |
| `embed` | [ ] | [ ] | [ ] | [ ] |
| `download-seed` | [ ] | [ ] | [ ] | [ ] |
| `import-seed` | [ ] | [ ] | [ ] | [ ] |
| `diagnostics` | N/A | [ ] | [ ] | [ ] |
| `reset-db` | N/A | [ ] | N/A | N/A |

#### Metrics
- [ ] `~/linkedout-data/metrics/daily/YYYY-MM-DD.jsonl` populated after operations
- [ ] `summary.json` updated by `linkedout status`
- [ ] Metric events include: `ts`, `metric`, `value`, and relevant context fields

#### Diagnostic report
- [ ] `linkedout diagnostics` produces all sections: System, Config, Database, Health, Recommendations
- [ ] Secrets are never included (only "configured" / "not configured")
- [ ] `--json` flag outputs valid JSON
- [ ] `--repair` flag detects and offers to fix common issues
- [ ] Report saved to `~/linkedout-data/reports/diagnostic-YYYYMMDD-HHMMSS.json`

#### Readiness reports
- [ ] Every major operation produces a report in `~/linkedout-data/reports/`
- [ ] Reports follow standard format: `operation`, `timestamp`, `duration_ms`, `counts`, `coverage_gaps`, `failures`, `next_steps`
- [ ] Setup readiness report includes precise numbers (not just pass/fail)

### Create: scripts/validate-observability.sh

**File to create:** `scripts/validate-observability.sh`

A bash script that automates the observability validation. It should:

1. Check that log files exist and are in the expected directory
2. Verify log format (human-readable, not JSON)
3. Check that report files follow the expected format
4. Verify metrics directory structure
5. Run `linkedout diagnostics --json` and check output format
6. Report pass/fail for each check

Make it runnable: `chmod +x scripts/validate-observability.sh`

Output should be a checklist-style report with pass/fail for each item.

### Gap handling

For each validation item that fails:
- If it's a quick fix (< 15 min): fix inline
- If it's a code change that affects multiple files: document the gap clearly in a comment block and note it in the sub-phase output
- Create GitHub issues for any non-trivial gaps found

---

## Verification

### Test suite (13D)
- [ ] `tests/README.md` documents all tiers, how to run locally, and what each tier catches
- [ ] Tier 1 + 2 configured to run on every push and PR (< 5 minutes total)
- [ ] Tier 3 configured to run nightly and on release branches
- [ ] No test requires a paid API key to pass in CI
- [ ] CI status badge in README reflects Tier 1 + 2

### Observability (13E)
- [ ] Every checkbox in the validation checklist above is verified (or gap documented)
- [ ] `scripts/validate-observability.sh` exists and is executable
- [ ] Gaps found are documented (as issues or inline TODOs)
- [ ] No silent failures — every operation that modifies data reports what it did

---

## Output Artifacts

- `tests/README.md` (new)
- `.github/workflows/ci.yml` (modified if needed)
- `scripts/validate-observability.sh` (new)
- Any inline fixes for quick gaps
- List of issues filed for non-trivial gaps

---

## Post-Completion Check

1. `tests/README.md` is accurate and matches actual test infrastructure
2. CI workflow triggers are correct (push + PR for Tier 1+2, nightly for Tier 3)
3. `scripts/validate-observability.sh` is executable and documented
4. All gaps are either fixed or tracked
