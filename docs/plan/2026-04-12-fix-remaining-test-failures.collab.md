# Fix Remaining 16 Test Failures — Detailed Execution Plan

## Context

6 easy tests already fixed (Clusters A + C). 16 remain across 3 clusters:
- **Cluster B:** 2 unit tests — python_env OperationCounts mismatch
- **Cluster D:** 9 integration tests — embed command bypasses test schema
- **Cluster E:** 5 skipped tests — stale `embedding` column references

---

## Cluster B: Python env install (2 unit tests)

### Problem
`install_dependencies()` was refactored: no longer runs `pip install uv` as a subprocess call. It finds uv via `shutil.which()` or venv path, then makes only 2 subprocess calls (requirements + editable). But source still reports `total=3` and tests expect `call_count == 3`.

### Changes

#### 1. Source: `backend/src/linkedout/setup/python_env.py`

**Line 131** — step2 failure path reports total=3, should be 2:
```
OLD: counts=OperationCounts(total=3, succeeded=2, failed=1),
NEW: counts=OperationCounts(total=2, succeeded=1, failed=1),
```

**Line 141** — success path reports total=3, should be 2:
```
OLD: counts=OperationCounts(total=3, succeeded=3),
NEW: counts=OperationCounts(total=2, succeeded=2),
```

(Line 112 already correct: `total=2, succeeded=1, failed=1`)

#### 2. Test: `backend/tests/linkedout/setup/test_python_env.py`

**Test 1 (`test_installs_via_uv_pipeline`, line 62-70):**
```
OLD: assert report.counts.succeeded == 3  # uv install, requirements, editable
     assert mock_run.call_count == 3
NEW: assert report.counts.succeeded == 2  # requirements, editable
     assert mock_run.call_count == 2
```

**Test 2 (`test_falls_back_to_pip_when_uv_fails`, line 72-93):**
Rewrite to mock `shutil.which` returning None (triggering pip fallback path) instead of mocking subprocess failure. The pip path makes 2 subprocess calls and returns `OperationCounts(total=2, succeeded=2)`.

```python
@patch('linkedout.setup.python_env.shutil.which', return_value=None)
@patch('linkedout.setup.python_env.subprocess.run')
def test_falls_back_to_pip_when_uv_fails(self, mock_run, mock_which, fake_repo):
    mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
    # Ensure venv uv doesn't exist either
    report = install_dependencies(fake_repo)
    assert report.counts.succeeded == 2
    assert report.counts.failed == 0
    assert mock_run.call_count == 2
```

Note: `fake_repo` has no `.venv/bin/uv` file, so the venv path check at line 90 already fails. Mocking `shutil.which` returning None ensures the system path check at line 92 also fails → falls through to `_install_via_pip()`.

### Verification
```bash
pytest tests/linkedout/setup/test_python_env.py::TestInstallDependencies -xvs
```

---

## Cluster D: Embed integration (9 tests)

### Problem
`embed_command` calls `cli_db_manager()` (3 times in embed.py: lines 130, 160, 219) which creates its own engine from `get_config().database_url`. This connects to the default schema, not the test schema where `integration_db_session` created the tables.

`cli_db_manager()` is in `src/shared/infra/db/cli_db.py:9-16`:
```python
def cli_db_manager() -> DbSessionManager:
    settings = get_config()
    engine = create_engine(settings.database_url, echo=settings.db_echo_log)
    return DbSessionManager(engine)
```

### Fix
Patch `cli_db_manager` in all 9 tests to return a `DbSessionManager` bound to the test schema engine. Add a fixture:

#### `backend/tests/integration/test_embed_command.py` — add fixture + update tests

**Add fixture after line 42:**
```python
@pytest.fixture
def patch_db(integration_db_engine):
    """Patch cli_db_manager so embed_command uses the test schema."""
    from shared.infra.db.db_session_manager import DbSessionManager
    test_manager = DbSessionManager(integration_db_engine)
    with patch('linkedout.commands.embed.cli_db_manager', return_value=test_manager):
        yield
```

**Update each test method signature** to include `patch_db` fixture. All 9 tests follow the same pattern — they already use `integration_db_session` and patch `get_embedding_provider` + `get_progress_path`. Add `patch_db` to each.

**All 9 test classes to update:**
1. `TestEmbedOpenAIE2E.test_embed_openai` (line 133)
2. `TestEmbedLocalE2E.test_embed_local` (line 170)
3. `TestEmbedDryRun.test_dry_run_no_db_writes` (line 200)
4. `TestEmbedForce.test_force_reembeds` (line 231)
5. `TestEmbedResume.test_resume_continues_from_checkpoint` (line 267)
6. `TestEmbedIdempotent.test_second_run_is_noop` (line 305)
7. `TestEmbedProviderSwitch.test_both_columns_populated` (line 330)
8. `TestEmbedZeroProfiles.test_empty_db_clean_exit` (line 370)
9. `TestReportArtifact.test_report_file_created` (line 401)

### Verification
```bash
pytest tests/integration/test_embed_command.py -xvs --override-ini=addopts= -m integration
```

---

## Cluster E: pgvector fixture + stale column refs (5 tests)

### Problem
1. `vector_column_ready` fixture tries `ALTER TABLE crawled_profile ALTER COLUMN embedding TYPE vector(1536)` — column doesn't exist (entity has `embedding_openai` and `embedding_nomic`, both already Vector type from create_all)
2. Test SQL in `test_affinity_integration.py` references `embedding` instead of `embedding_openai`

### Changes

#### 1. Fixture: `backend/tests/integration/linkedout/intelligence/conftest.py`

**Lines 48-62** — simplify `vector_column_ready`:
```python
@pytest.fixture(scope='session')
def vector_column_ready(integration_db_engine, integration_db_session, pgvector_available, intelligence_test_data):
    """Ensure pgvector is available and search_path includes public for vector types.

    The embedding columns (embedding_openai, embedding_nomic) are already
    Vector() type from the entity definition via Base.metadata.create_all().
    """
    if not pgvector_available:
        return False
    try:
        integration_db_session.execute(text(f"SET search_path TO {_TEST_SCHEMA}, public"))
        integration_db_session.commit()
        return True
    except Exception:
        integration_db_session.rollback()
        return False
```

#### 2. Test SQL: `backend/tests/integration/linkedout/intelligence/test_affinity_integration.py`

4 replacements (all `embedding` → `embedding_openai`):
- Line 225: `SET embedding =` → `SET embedding_openai =`
- Line 232: `SET embedding =` → `SET embedding_openai =`
- Line 281: `SET embedding =` → `SET embedding_openai =`
- Line 287: `(embedding <=>` → `(embedding_openai <=>`

#### 3. Embedding provider config — CRITICAL

Both `AffinityScorer._get_embedding_column()` and `vector_tool._get_embedding_column()` read the embedding provider from config at runtime. `.env.integration` sets `LINKEDOUT_EMBEDDING__PROVIDER=local` → they return `embedding_nomic`. But the tests write 1536-dim vectors to `embedding_openai`.

**Fix:** Add a session-scoped autouse fixture in `tests/integration/linkedout/intelligence/conftest.py`:

```python
@pytest.fixture(autouse=True, scope='session')
def _use_openai_embedding_provider():
    """Force openai provider so embedding column tests use embedding_openai."""
    import os
    old = os.environ.get("LINKEDOUT_EMBEDDING__PROVIDER")
    os.environ["LINKEDOUT_EMBEDDING__PROVIDER"] = "openai"
    yield
    if old is None:
        os.environ.pop("LINKEDOUT_EMBEDDING__PROVIDER", None)
    else:
        os.environ["LINKEDOUT_EMBEDDING__PROVIDER"] = old
```

### Verification
```bash
pytest tests/integration/linkedout/intelligence/test_affinity_integration.py::TestEmbeddingSimilaritySignal \
  tests/integration/linkedout/intelligence/test_search_integration.py::TestVectorSearchUserScoped \
  -xvs --override-ini=addopts= -m integration
```

---

## Execution Order

1. **Cluster B** (source + test fix, self-contained, no DB)
2. **Cluster E** (fixture + test SQL fix, need pgvector DB)
3. **Cluster D** (test fixture addition, most files touched)

## Final Verification

```bash
precommit-tests
```

Expected: 0 failures, only 6 smoke test skips (need demo DB setup — expected).
