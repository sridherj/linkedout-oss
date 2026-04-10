# Sub-Phase 02: VERSION File & Version Utilities

**Source task:** 10B
**Complexity:** S
**Dependencies:** Design Gate (sub-phase 01) must be approved

## Objective

Establish the single source of truth for LinkedOut's installed version. Create the `VERSION` file at repo root and a version reading utility module.

## Context

Read `_shared_context.md` for project-level context. Key points:
- `linkedout version` displays ASCII logo from `docs/brand/logo-ascii.txt` per CLI surface decision
- Config path shown is `~/linkedout-data/config/config.yaml` per env-config decision
- Version should be importable: `from linkedout.version import __version__`

## Deliverables

### Files to Create

1. **`VERSION`** (repo root)
   - Content: `0.1.0` (just the semver string, no newline cruft)

2. **`backend/src/linkedout/version.py`**
   - Reads `VERSION` file from repo root
   - Exposes `__version__` string
   - `get_version_info() -> dict` returning:
     - `version`: from VERSION file
     - `python_version`: from `sys.version`
     - `pg_version`: from database (or "not connected" if unavailable)
     - `install_path`: repo root path
     - `config_path`: `~/linkedout-data/config/config.yaml`
     - `data_dir`: `~/linkedout-data/`

### Files to Modify

3. **`backend/pyproject.toml`**
   - Add/ensure `linkedout` CLI entry point (or note for Phase 6E integration)

4. **`backend/src/dev_tools/cli.py`**
   - Wire `linkedout version` command to use `version.py`
   - `linkedout version` prints: ASCII logo + version info (human-readable)
   - `linkedout version --json` returns structured JSON

### Tests to Create

5. **`backend/tests/unit/upgrade/test_version.py`**
   - `VERSION` file parsing works correctly
   - `get_version_info()` returns correct structure
   - Missing `VERSION` file raises clear error
   - `__version__` matches `VERSION` file content

## Acceptance Criteria

- [ ] `VERSION` file exists at repo root with content `0.1.0`
- [ ] `from linkedout.version import __version__` works and returns `"0.1.0"`
- [ ] `get_version_info()` returns dict with all required fields
- [ ] `linkedout version` displays ASCII logo + version info
- [ ] `linkedout version --json` returns structured JSON
- [ ] Unit tests pass

## Verification

```bash
# Check VERSION file
cat VERSION
# Should output: 0.1.0

# Check import works
cd backend && python -c "from linkedout.version import __version__; print(__version__)"
# Should output: 0.1.0

# Run unit tests
cd backend && python -m pytest tests/unit/upgrade/test_version.py -v
```

## Notes

- The `VERSION` file is the single source of truth — `pyproject.toml` version should reference it or be kept in sync
- `pg_version` in `get_version_info()` should gracefully handle no DB connection (return "not connected")
- The ASCII logo path (`docs/brand/logo-ascii.txt`) may not exist yet — handle gracefully
