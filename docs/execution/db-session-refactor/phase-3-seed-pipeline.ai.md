# Phase 3: Fix Seed Pipeline SQL Guard + Dynamic Fixture Generation

## RCA

RCA #2 — `_build_staging_upsert_sql()` generates invalid SQL when the column intersection between `_seed_staging` and `public` schemas is empty. The static test fixture `test-seed-core.dump` was built against an older schema, causing empty column lists.

## Scope

4 files. Code guard + test fixture refactor.

## Dependencies

None. This phase is independent and can run in parallel with Phases 1 and 2.

## Changes

### 1. File: `src/linkedout/commands/import_seed.py`

Add an empty-column guard at the top of `_build_staging_upsert_sql()` (line 100). The current function starts:

```python
def _build_staging_upsert_sql(table: str, columns: list[str]) -> str:
    col_list = ", ".join(columns)
```

Change to:

```python
def _build_staging_upsert_sql(table: str, columns: list[str]) -> str | None:
    """Build upsert SQL from staging to public. Returns None if no columns overlap."""
    if not columns:
        return None
    col_list = ", ".join(columns)
```

Then update the caller that uses this function. Find where `_build_staging_upsert_sql` is called (search for it in the same file). The caller should check for `None` and skip with a warning:

```python
sql = _build_staging_upsert_sql(table, columns)
if sql is None:
    logger.warning(f"Skipping table '{table}': no overlapping columns between staging and public schemas")
    continue  # or return appropriate zero-counts
```

### 2. File: `tests/fixtures/generate_test_seed.py`

This file already has all the logic to create staging tables from entity metadata, insert synthetic data, and call `pg_dump`. Refactor the core functions to be importable:

- Ensure `_create_schema(db_url)`, `_insert_synthetic_data(db_url)`, `_pg_dump(db_url, output_path)` are clean functions that can be called from test fixtures
- The file is already structured this way — just verify the `if __name__ == "__main__"` block at the bottom keeps standalone execution working
- The key functions needed by the test fixture are: `_create_schema()`, `_insert_synthetic_data()`, and `_pg_dump()`

### 3. File: `tests/integration/cli/test_seed_pipeline.py`

Replace the static fixture loading with dynamic generation. The current fixture at line 32-35:

```python
@pytest.fixture(scope='module')
def fixture_path():
    assert FIXTURE_PATH.exists(), f'Test fixture not found: {FIXTURE_PATH}'
    return FIXTURE_PATH
```

Replace with a module-scoped fixture that generates the dump dynamically:

```python
@pytest.fixture(scope='module')
def fixture_path(integration_db_engine):
    """Generate a test seed dump dynamically from current schema."""
    import tempfile
    from tests.fixtures.generate_test_seed import _create_schema, _insert_synthetic_data, _pg_dump

    db_url = str(integration_db_engine.url)
    output_path = Path(tempfile.mktemp(suffix='.dump'))

    try:
        _create_schema(db_url)
        _insert_synthetic_data(db_url)
        _pg_dump(db_url, output_path)
        assert output_path.exists(), f'Generated fixture not found: {output_path}'
        yield output_path
    finally:
        output_path.unlink(missing_ok=True)
```

Also update the `expected_counts` fixture — since we're generating dynamically, counts come from the generation code, not a static manifest. Check `generate_test_seed.py` for the synthetic data counts and either:
- Have `generate_test_seed.py` return/write the manifest alongside the dump
- Or hardcode expected counts based on the generation logic

**Important:** The `integration_db_engine` fixture is from `tests/integration/conftest.py` — it provides a PostgreSQL engine with a test schema. Make sure the dynamic generation uses the same database URL.

### 4. File: `tests/fixtures/test-seed-core.dump`

Delete this stale file. It was built against a previous schema version and causes the empty column intersection.

```bash
rm tests/fixtures/test-seed-core.dump
```

If `seed-manifest.json` is also stale and tied to this dump, it can be deleted too — but verify no other tests reference it first.

## Verification

```bash
# Run seed pipeline tests specifically
cd ./backend && uv run pytest tests/integration/cli/test_seed_pipeline.py -x -v -m integration 2>&1 | tail -30

# Verify the import_seed module guard works
cd ./backend && uv run python -c "
from linkedout.commands.import_seed import _build_staging_upsert_sql
result = _build_staging_upsert_sql('test_table', [])
assert result is None, f'Expected None for empty columns, got: {result}'
print('Empty column guard works correctly')
"
```

**Expected:** All 5 seed pipeline tests pass (or skip gracefully if PostgreSQL not available). The empty column guard returns `None` for empty column lists.
