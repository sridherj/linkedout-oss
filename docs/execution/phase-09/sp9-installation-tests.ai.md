# Sub-Phase 9: Installation Test Suite

**Phase:** 9 — AI-Native Setup Flow
**Plan tasks:** 9R (Installation Test Suite)
**Dependencies:** sp8 (orchestrator must be complete)
**Blocks:** —
**Can run in parallel with:** —

## Objective
Build a dedicated test suite for the setup/installation flow. These are integration tests that touch the real OS — too heavy for every CI push, designed for nightly schedule. They use isolated data directories and databases to avoid interfering with real data. This is L complexity due to the breadth of test scenarios and platform-specific considerations.

## Context
- Read shared context: `docs/execution/phase-09/_shared_context.md`
- Read plan (9R section): `docs/plan/phase-09-setup-flow.md`
- Read UX design doc: `docs/design/setup-flow-ux.md`
- Read all setup modules from sp2-sp8 (understand what's being tested)
- Read existing test patterns: `backend/tests/` (follow conventions)

## Deliverables

### 1. `tests/installation/conftest.py` (NEW)

Shared fixtures for installation tests.

**Fixtures:**

```python
@pytest.fixture
def temp_data_dir(tmp_path):
    """Isolated ~/linkedout-data-test-{uuid}/ for each test."""
    data_dir = tmp_path / f"linkedout-data-test-{uuid4().hex[:8]}"
    data_dir.mkdir()
    (data_dir / "config").mkdir()
    (data_dir / "logs").mkdir()
    (data_dir / "reports").mkdir()
    (data_dir / "state").mkdir()
    (data_dir / "uploads").mkdir()
    yield data_dir
    # Cleanup handled by tmp_path

@pytest.fixture
def test_db(temp_data_dir):
    """Isolated PostgreSQL database linkedout_test_{uuid}."""
    db_name = f"linkedout_test_{uuid4().hex[:8]}"
    # Create test database
    subprocess.run(["createdb", db_name], check=True)
    db_url = f"postgresql://localhost/{db_name}"
    yield db_url, db_name
    # Cleanup: drop test database
    subprocess.run(["dropdb", "--if-exists", db_name], check=False)

@pytest.fixture
def mock_github_releases(tmp_path):
    """Serve seed data from local files (no network)."""
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    # Create minimal test seed files
    ...
    yield seed_dir

@pytest.fixture
def mock_openai():
    """Validate key format without real API call."""
    with patch("linkedout.setup.api_keys.validate_openai_key") as mock:
        mock.return_value = True
        yield mock
```

**Note:** All fixtures create isolated resources. No test touches the real `~/linkedout-data/` or `linkedout` database.

### 2. `tests/installation/test_fresh_install.py` (NEW)

End-to-end fresh install smoke test.

**Tests:**
- `test_fresh_install_happy_path` — Provision clean env, mock user inputs, run full setup orchestrator, assert readiness report has zero gaps
- `test_fresh_install_local_embeddings` — Same but with local embedding provider
- `test_fresh_install_openai_embeddings` — Same but with OpenAI provider (mock API)
- `test_fresh_install_no_contacts` — Skip contacts import, verify everything else works
- `test_fresh_install_produces_readiness_report` — Verify report file exists with expected fields

Each test ends by reading the readiness report JSON and asserting expected values.

### 3. `tests/installation/test_prerequisites.py` (NEW)

Prerequisite detection tests.

**Tests:**
- `test_detect_current_platform` — Verify correct OS detection on current system
- `test_detect_python_version` — Verify current Python version detected correctly
- `test_missing_postgres` — Mock missing PostgreSQL, verify `blockers` list
- `test_wrong_python_version` — Mock Python 3.9, verify `blockers` list
- `test_missing_pgvector` — Mock PostgreSQL without pgvector, verify detection
- `test_insufficient_disk_space` — Mock 500MB free, verify `sufficient=False`
- `test_sufficient_disk_space` — Mock 10GB free, verify `sufficient=True, recommended=True`
- `test_all_prerequisites_met` — Verify `ready=True, blockers=[]`

### 4. `tests/installation/test_idempotency.py` (NEW)

Re-run safety tests.

**Tests:**
- `test_second_run_skips_completed` — Run setup twice, second run shows "skipping" for all steps
- `test_second_run_produces_fresh_report` — Second run generates new readiness report
- `test_second_run_no_data_loss` — Compare DB counts before and after second run
- `test_second_run_no_duplicates` — Import same CSV twice, verify no duplicate profiles
- `test_second_run_fast` — Second run completes in <5 seconds (assert wall time)

### 5. `tests/installation/test_partial_recovery.py` (NEW)

Interrupted install recovery tests.

**Tests:**
- `test_resume_after_db_setup` — Complete through DB, interrupt, resume, verify picks up at next step
- `test_resume_after_import` — Complete through CSV import, interrupt, resume
- `test_corrupted_state_file` — Corrupt `setup-state.json`, verify graceful recovery (starts from scratch)
- `test_partial_migration` — Interrupt during migrations, resume, verify all migrations applied
- `test_partial_embedding` — Interrupt during embedding, resume, verify remaining profiles embedded

### 6. `tests/installation/test_permissions.py` (NEW)

Security and permission tests.

**Tests:**
- `test_secrets_yaml_permissions` — Verify `secrets.yaml` has `chmod 600` after setup
- `test_no_secrets_in_logs` — Grep all log files for API key patterns, assert none found
- `test_no_secrets_in_diagnostic` — Generate diagnostic file, verify no sensitive data
- `test_no_secrets_in_readiness_report` — Verify report JSON has boolean flags, not actual keys
- `test_config_yaml_no_world_readable` — Verify config.yaml permissions

### 7. `tests/installation/test_degraded.py` (NEW)

Degraded environment tests.

**Tests:**
- `test_no_network_seed_download` — Mock network timeout during seed download, verify actionable error
- `test_invalid_openai_key` — Provide bad key, verify clear error message with retry option
- `test_invalid_csv_format` — Provide non-LinkedIn CSV, verify format guidance
- `test_empty_csv` — Provide empty CSV, verify graceful handling
- `test_db_connection_refused` — Mock PostgreSQL down, verify error message
- `test_missing_generate_skills` — Remove `bin/generate-skills`, verify skill installation skipped with message

### 8. `tests/installation/README.md` (NEW)

Documentation for running installation tests.

**Contents:**
- What these tests do and don't test
- Prerequisites (real PostgreSQL, Python 3.11+)
- How to run: `pytest tests/installation/ -v --tb=long`
- How to run specific categories: `pytest tests/installation/test_prerequisites.py -v`
- CI integration: nightly workflow, not in main CI
- Test isolation: temp data dirs, temp databases, mock APIs
- Matrix: Ubuntu 24.04 + macOS-latest x Python 3.11/3.12/3.13 x PostgreSQL 16/17

### 9. `tests/installation/__init__.py` (NEW)

Empty package init.

## Verification
1. `pytest tests/installation/test_prerequisites.py -v` passes
2. `pytest tests/installation/test_permissions.py -v` passes
3. `pytest tests/installation/ -v --tb=long` — full suite passes
4. All tests use isolated data dirs (no `~/linkedout-data/` touched)
5. All tests clean up databases after themselves

## Notes
- These tests are NOT in `backend/tests/` — they're at the repo root in `tests/installation/` because they test the full system, not just backend code.
- Tests require a real PostgreSQL instance. Skip gracefully if not available (`pytest.mark.skipif`).
- Use `pytest.mark.slow` for tests that take >10 seconds.
- Mock external APIs (OpenAI, Apify, GitHub Releases) — never make real API calls in tests.
- The readiness report is the primary test oracle — most tests end by asserting against it.
- Platform-specific tests should use `pytest.mark.skipif(platform != "linux")` etc.
- CI workflow definition is deferred to Phase 13 — just document the intended matrix in README.md.
- Follow existing pytest conventions from `backend/tests/` (conftest patterns, fixture naming, assertion style).
