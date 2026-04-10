# SP4: Multi-Platform CI & End-to-End Testing

**Phase:** 13 — Polish & Launch
**Sub-phase:** 4 of 6
**Dependencies:** SP3 (test suite validation must confirm test infrastructure is sound)
**Estimated effort:** ~3 hours
**Shared context:** `_shared_context.md`

---

## Scope

Create GitHub Actions workflows for multi-platform installation CI (12 matrix combinations) and an end-to-end flow test that exercises the complete user journey. These are the definitive "does the whole thing work?" gates before release.

**Tasks from phase plan:** 13A (multi-platform CI), 13B (e2e flow testing)

---

## Part 1: Multi-Platform Installation CI (13A)

### Required reading
- `tests/installation/` — Phase 9R installation test suite (should exist from Phase 9)
- `.github/workflows/ci.yml` — Existing Tier 1+2 CI
- `docs/decision/env-config-design.md` — Config expectations
- `docs/decision/2026-04-07-embedding-model-selection.md` — nomic model details

### Create: .github/workflows/installation-test.yml

**File to create:** `.github/workflows/installation-test.yml`

#### CI Matrix

| Axis | Values |
|------|--------|
| OS | `ubuntu-24.04`, `macos-latest` |
| Python | `3.11`, `3.12`, `3.13` |
| PostgreSQL | `16`, `17` |

Total: 2 OS x 3 Python x 2 PostgreSQL = **12 matrix jobs**

#### Triggers
- **Nightly schedule:** `cron: '0 4 * * *'` (4 AM UTC)
- **Manual dispatch:** `workflow_dispatch` with optional matrix parameter overrides
- **Release branches:** push to `release/*` branches

#### Workflow design

```yaml
name: Installation Tests (Tier 3)

on:
  schedule:
    - cron: '0 4 * * *'
  workflow_dispatch:
  push:
    branches: ['release/*']

jobs:
  installation-matrix:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-24.04, macos-latest]
        python-version: ['3.11', '3.12', '3.13']
        postgres-version: ['16', '17']
    runs-on: ${{ matrix.os }}
    timeout-minutes: 30
    steps:
      # ... (see implementation notes below)
```

#### Steps per job

1. **Checkout** — `actions/checkout@v4`
2. **Install PostgreSQL** — OS-specific:
   - Ubuntu: `sudo apt-get install postgresql-${{ matrix.postgres-version }} postgresql-${{ matrix.postgres-version }}-pgvector`
   - macOS: `brew install postgresql@${{ matrix.postgres-version }} pgvector`
3. **Setup Python** — `actions/setup-python@v5` with `python-version: ${{ matrix.postgres-version }}`
4. **Run installation test** — Execute `tests/installation/test_fresh_install.sh`
   - Simulates: `git clone` -> setup script -> `linkedout status`
5. **Assert readiness** — Parse the readiness report JSON and verify: zero gaps, expected table counts, CLI commands functional
6. **Upload artifacts on failure** — Upload readiness reports and logs as workflow artifacts

#### Test-to-CI mapping

| Test | Runs In CI? | Matrix Scope |
|------|-------------|-------------|
| Fresh install smoke test | Yes | All 12 matrix jobs |
| Prerequisite detection | Yes | All 12 matrix jobs |
| Idempotency test | Yes | ubuntu-24.04 only |
| Partial failure recovery | Yes | ubuntu-24.04 only |
| Permission tests | Yes | All 12 matrix jobs |
| Degraded environment | Yes | ubuntu-24.04 only |
| Readiness report assertion | Yes | All 12 matrix jobs |
| Upgrade path test | No | Manual/release only |

#### Implementation notes
- PostgreSQL installation: `apt-get` on Ubuntu, `brew` on macOS. Pin major version.
- pgvector: `postgresql-{ver}-pgvector` on Ubuntu, `brew install pgvector` on macOS
- Python: `actions/setup-python@v5`
- Seed data: use a minimal test seed fixture (NOT the full 50MB download) to keep CI fast
- API keys: skip OpenAI/Apify — tests use local nomic embeddings only
- Timeout: 30 minutes per job (installation + embeddings on CPU can be slow)
- `fail-fast: false` — run all matrix combinations even if some fail

---

## Part 2: End-to-End Flow Testing (13B)

### Create: tests/installation/test_e2e_flow.sh

**File to create:** `tests/installation/test_e2e_flow.sh`

A bash script that exercises the complete user journey end-to-end.

#### Test flow

```bash
# Step 1: Fresh setup
# Run setup equivalent (scripts/system-setup.sh + CLI commands)
# Assert: readiness report has zero gaps

# Step 2: Import connections
# linkedout import-connections tests/fixtures/sample-connections.csv
# Assert: report shows expected import counts

# Step 3: Generate embeddings
# linkedout embed --provider local
# Assert: embedding coverage = 100% in status

# Step 4: Compute affinity
# linkedout compute-affinity
# Assert: all connections have affinity scores

# Step 5: CLI smoke tests
# linkedout status --json → verify JSON output has expected fields, non-zero counts
# linkedout diagnostics --json → verify all health checks pass

# Step 6: Simulate upgrade
# Modify VERSION file to simulate version bump
# linkedout migrate --dry-run → no pending migrations (clean state)

# Step 7: Re-run setup (idempotency)
# Re-run setup steps
# Assert: all steps skip (already complete)
# Assert: readiness report identical to Step 1
```

#### Implementation notes
- Each step checks the exit code AND parses the report JSON
- On failure, dump `~/linkedout-data/logs/` and the last readiness report to stdout
- Use clear step labels for CI output (e.g., `echo "=== Step 3: Generate embeddings ==="`)
- Exit with non-zero on first failure (but dump diagnostics first)

### Create: tests/installation/test_upgrade_path.sh

**File to create:** `tests/installation/test_upgrade_path.sh`

Tests the upgrade path: install v0.1.0, then upgrade to current HEAD.
- This test is too slow for nightly; runs on `release/*` branches or manual dispatch only.

### Create: test fixtures

**Files to create/verify:**
- `tests/fixtures/sample-connections.csv` — Small LinkedIn-format CSV (50-100 rows) with realistic but fake data
- `tests/fixtures/sample-seed.sqlite` — Minimal seed data matching the CSV connections (small enough for CI)

If these fixtures already exist from Phase 9, verify they're sufficient. If not, create them.

**CSV format** — Must match LinkedIn's export format:
```csv
First Name,Last Name,URL,Email Address,Company,Position,Connected On
Jane,Doe,https://www.linkedin.com/in/janedoe,,,Software Engineer at Acme Corp,Acme Corp,01 Jan 2024
```

### Add e2e job to CI workflow

**File to modify:** `.github/workflows/installation-test.yml`

Add an `e2e` job that:
- Runs after the matrix jobs (using `needs: installation-matrix`)
- Runs on `ubuntu-24.04` + Python 3.12 + PostgreSQL 17 only (representative, not exhaustive)
- Executes `tests/installation/test_e2e_flow.sh`
- Uploads diagnostic artifacts on failure

---

## Verification

### 13A (Multi-platform CI)
- [ ] `.github/workflows/installation-test.yml` exists with correct matrix (2 OS x 3 Python x 2 PG = 12)
- [ ] Triggers: nightly schedule, manual dispatch, release branch push
- [ ] Each matrix job has 30-minute timeout
- [ ] Failed jobs upload readiness reports and logs as artifacts
- [ ] No test requires a paid API key
- [ ] `fail-fast: false` so all combinations run

### 13B (E2E testing)
- [ ] `tests/installation/test_e2e_flow.sh` exists and covers all 7 steps
- [ ] `tests/installation/test_upgrade_path.sh` exists
- [ ] Test fixtures exist: `sample-connections.csv`, `sample-seed.sqlite`
- [ ] E2E job in CI runs after matrix, gated on matrix passing
- [ ] Full flow completes in < 15 minutes on CI
- [ ] Test failures produce enough diagnostic output to debug remotely

---

## Output Artifacts

- `.github/workflows/installation-test.yml` (new)
- `tests/installation/test_e2e_flow.sh` (new)
- `tests/installation/test_upgrade_path.sh` (new)
- `tests/fixtures/sample-connections.csv` (new or verified)
- `tests/fixtures/sample-seed.sqlite` (new or verified)

---

## Post-Completion Check

1. Workflow YAML is valid (check with `actionlint` if available, or manual review)
2. All test scripts are executable (`chmod +x`)
3. No hardcoded API keys or secrets in test scripts
4. Seed data test fixtures are small enough for CI (not full 50MB dataset)
5. Matrix covers all specified combinations
