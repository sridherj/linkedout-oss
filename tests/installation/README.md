# Installation Tests

Integration tests for the LinkedOut setup/installation flow. These tests
exercise the full setup orchestrator and its component modules against
isolated data directories and databases.

## What these tests cover

- **Prerequisites detection** — OS, Python, PostgreSQL, disk space checks
- **Fresh install flow** — End-to-end orchestrator logic with mocked steps
- **Idempotency** — Second-run skip logic, no data loss, no duplicates
- **Partial recovery** — Resume after interruption at any step
- **Permissions** — secrets.yaml chmod 600, no secrets in logs/reports
- **Degraded environments** — Network failures, bad keys, missing tools

## What these tests do NOT cover

- Actual PostgreSQL database operations (use `@requires_postgres` marker for those)
- Real API calls to OpenAI, Apify, or GitHub
- Web frontend behavior
- Chrome extension functionality

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ (for `@requires_postgres` tests only)
- The `linkedout` backend package installed in the current environment

## Running the tests

Full suite:

```bash
pytest tests/installation/ -v --tb=long
```

Specific category:

```bash
pytest tests/installation/test_prerequisites.py -v
pytest tests/installation/test_permissions.py -v
pytest tests/installation/test_degraded.py -v
```

Skip slow tests:

```bash
pytest tests/installation/ -v -m "not slow"
```

Only tests requiring PostgreSQL:

```bash
pytest tests/installation/ -v -m requires_postgres
```

## Test isolation

Every test uses isolated resources:

- **Temp data directories** — Each test gets its own `tmp_path`-based data
  directory. No test reads from or writes to the real `~/linkedout-data/`.
- **Temp databases** — Tests that need PostgreSQL create
  `linkedout_test_{uuid}` databases and drop them after the test.
- **Mocked APIs** — All external API calls (OpenAI, Apify, GitHub) are
  mocked. No real network requests are made.
- **Mocked subprocesses** — Tests that verify CLI behavior mock
  `subprocess.run` to avoid spawning real processes.

## CI integration

These tests are designed for a **nightly CI schedule**, not the main CI
pipeline (they are heavier than unit tests).

Target matrix:

| OS              | Python    | PostgreSQL |
|-----------------|-----------|------------|
| Ubuntu 24.04    | 3.11      | 16         |
| Ubuntu 24.04    | 3.12      | 16         |
| Ubuntu 24.04    | 3.13      | 17         |
| macOS-latest    | 3.11      | 16         |
| macOS-latest    | 3.12      | 17         |
| macOS-latest    | 3.13      | 17         |

CI workflow definition is deferred to Phase 13.

## Adding new tests

Follow these conventions:

1. Place tests in the appropriate file by category
2. Use `temp_data_dir` fixture for isolated data directories
3. Use `test_db` fixture for isolated PostgreSQL databases
4. Mock all external calls — never hit real APIs
5. Mark slow tests with `@pytest.mark.slow`
6. Mark PostgreSQL-dependent tests with `@requires_postgres` (from conftest)
7. Test names should describe the scenario: `test_<scenario>_<expected_behavior>`
