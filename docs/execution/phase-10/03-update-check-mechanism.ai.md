# Sub-Phase 03: Update Check Mechanism

**Source task:** 10C
**Complexity:** M
**Dependencies:** Sub-phase 02 (VERSION file & version utilities)

## Objective

Implement a non-blocking update check that runs on skill invocation. Compares the local `VERSION` file against the latest GitHub Release tag. Results are cached to avoid excessive API calls.

## Context

Read `_shared_context.md` for project-level context. Key points:
- GitHub API is unauthenticated for v1 (60 req/hour rate limit, fine for single user)
- Optional `GITHUB_TOKEN` env var for higher limits
- State files live under `~/linkedout-data/state/`
- Uses loguru for logging
- Must never block or prevent usage

## Deliverables

### Files to Create

1. **`backend/src/linkedout/upgrade/__init__.py`**
   - Package init, re-export key functions

2. **`backend/src/linkedout/upgrade/update_checker.py`**
   - `UpdateInfo` dataclass: `latest_version`, `current_version`, `release_url`, `is_outdated`, `checked_at`
   - `check_for_update() -> UpdateInfo | None`
     - Calls GitHub Releases API for latest release
     - Compares semver against local `VERSION`
     - Caches result to `~/linkedout-data/state/update-check.json`
     - Returns `None` on network error (never raises)
   - `get_cached_update() -> UpdateInfo | None`
     - Reads cache file
     - Returns cached result if < 1 hour old
     - Returns `None` if stale or missing
   - `save_update_cache(info: UpdateInfo)`
     - Writes to `~/linkedout-data/state/update-check.json`
   - Cache file format:
     ```json
     {
       "checked_at": "2026-04-07T14:30:00Z",
       "latest_version": "0.2.0",
       "current_version": "0.1.0",
       "release_url": "https://github.com/...",
       "is_outdated": true
     }
     ```
   - Throttle: max one API call per hour (use cache for subsequent checks)
   - Respect `GITHUB_TOKEN` env var if set (add to Authorization header)

### Tests to Create

3. **`backend/tests/unit/upgrade/test_update_checker.py`**
   - Mocked GitHub API response parsing (outdated, up-to-date, pre-release)
   - Cache read/write round-trip
   - Throttle logic (cache < 1h returns cached, cache > 1h triggers fresh check)
   - Network error returns `None` (no exception)
   - Semver comparison edge cases (0.1.0 vs 0.1.0, 0.2.0 vs 0.1.0, 1.0.0-rc1)
   - `GITHUB_TOKEN` used when available

## Acceptance Criteria

- [ ] `check_for_update()` calls GitHub API and returns `UpdateInfo`
- [ ] Check is throttled to max once per hour via cache
- [ ] If outdated, returns `UpdateInfo` with `is_outdated=True`
- [ ] If up-to-date, returns `UpdateInfo` with `is_outdated=False`
- [ ] If network error, returns `None` (never raises, never blocks)
- [ ] Cache file written to `~/linkedout-data/state/update-check.json`
- [ ] `GITHUB_TOKEN` env var respected if set
- [ ] All unit tests pass with mocked HTTP

## Verification

```bash
# Run unit tests
cd backend && python -m pytest tests/unit/upgrade/test_update_checker.py -v

# Verify no real network calls in tests
grep -r "requests.get\|httpx\|urllib" tests/unit/upgrade/test_update_checker.py
# Should only appear in mock/patch contexts
```

## Notes

- The GitHub repo URL will need to be configurable or defaulted to the LinkedOut OSS repo
- Use `httpx` or `urllib` for HTTP calls — whichever the project already uses
- Semver comparison: use `packaging.version.Version` or a lightweight semver parser
- This module is extended in sub-phase 06 (Snooze Support) — keep the interface clean for that
