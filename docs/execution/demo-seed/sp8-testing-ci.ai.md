# Sub-phase 8: Testing & CI

## Metadata

| Field | Value |
|-------|-------|
| Sub-phase | SP8 |
| Dependencies | SP1-SP5, SP7 (all user-facing code and docs must be complete) |
| Estimated effort | 2 sessions (~6 hours) |
| Branch | main |
| Plan reference | `docs/plan/2026-04-08-demo-seed-plan.md` — Sub-phase 8 |

## Objective

Comprehensive test coverage for the demo experience: a synthetic test dump for development, unit/integration tests for all demo flows, and a CI end-to-end smoke test that proves the demo works on Ubuntu and macOS.

## Context

Individual sub-phases (SP1-SP5) include their own unit tests. This sub-phase consolidates integration tests, creates the synthetic test dump fixture, and adds a CI workflow for end-to-end smoke testing.

### Key existing files (read these before implementing)

- `backend/tests/` — Existing test structure
- `.github/workflows/` — Existing CI workflows
- All demo modules created in SP1-SP5

## Tasks

### 1. Create synthetic test dump

Create a script `backend/tests/fixtures/generate_test_demo_dump.py` that:

- Builds a temporary DB
- Inserts ~10 profiles, ~50 experiences, ~20 education records, ~30 skills, ~10 connections, ~100 companies
- Includes the system user profile (founder/CTO composite) with known affinity patterns
- Pre-computes local embeddings and affinity scores
- Runs `pg_dump` to produce `backend/tests/fixtures/demo-seed-test.dump`
- This dump is committed to the repo (small, ~1-2 MB) so all tests can use it

### 2. Unit tests (no Postgres needed)

Ensure these exist (some created in earlier sub-phases, consolidate/fill gaps):

- `test_demo_config.py` — demo_mode parsing, get_demo_db_url, set_demo_mode
- `test_demo_offer_flow.py` — mock user input (accept/decline), verify D1-D5 sequence
- `test_step_numbering.py` — verify "Step N of 4" vs "Step N of 14" logic
- `test_nudge_footer.py` — footer appears in demo mode, absent otherwise
- `test_transition_flow.py` — mock transition accept/decline, verify config changes
- `test_sample_queries.py` — verify sample query content covers all 3 pillars
- `test_demo_rerun_noop.py` — re-running setup in demo mode (decline transition) is fast

### 3. Integration tests (require Postgres)

- `test_restore_demo.py` — create/drop/restore cycle with the synthetic test dump
- `test_reset_demo.py` — reset restores to original state
- `test_use_real_db.py` — config switch and optional drop
- `test_demo_query.py` — restore synthetic dump, run a semantic search query, verify results returned (proves embeddings + pgvector + full search stack work)
- `test_demo_stats.py` — verify get_demo_stats returns correct counts after restore
- `test_prerequisites_pg_restore.py` — verify pg_restore check works

### 4. CI end-to-end smoke test

Create `.github/workflows/demo-smoke-test.yml`:

- Runs on: `ubuntu-latest` and `macos-latest`
- Triggered on: PRs that touch `backend/src/linkedout/demo/`, `backend/src/linkedout/setup/`, or `backend/src/linkedout/commands/*demo*`
- Steps:
  1. Install Python 3.12, PostgreSQL 16, pgvector
  2. Clone repo
  3. Run `linkedout setup` with mock input accepting demo (use synthetic test dump, not the real ~100MB dump — keep CI fast)
  4. Verify demo mode is active: `linkedout status --json | jq '.demo_mode'` == true
  5. Run query 1: `linkedout query "ML engineer"` -> verify non-empty results
  6. Run query 2: `linkedout query "Series B startup"` -> verify non-empty results
  7. Run `linkedout reset-demo` -> verify DB restored
  8. Run `linkedout use-real-db --drop-demo` -> verify demo DB gone
- Timeout: 10 minutes
- Uses the synthetic test dump from fixtures (not GitHub Releases download)

### 5. Document manual verification checklist

For the REAL dump from SP6 (not automated — done once before publishing):

- Restore the real dump on a clean Ubuntu 24.04 machine
- Run all 3 sample queries from demo-help
- Verify affinity scores are intuitive for the founder/CTO demo profile
- Verify the nudge footer appears
- Run transition flow and complete full setup

## Verification Checklist

- [ ] All unit tests pass without Postgres
- [ ] All integration tests pass with a running Postgres
- [ ] CI smoke test passes on Ubuntu (latest) and macOS (latest)
- [ ] CI smoke test executes 2 real queries against the demo DB and verifies results
- [ ] Synthetic test dump is committed and is < 2 MB

## Design Notes

- **Test dump vs real dump:** The synthetic test dump (~10 profiles) is for fast CI. The real dump (~2K profiles) from SP6 is for manual verification only.
- **CI strategy:** Using the synthetic dump keeps CI fast (~2 min) and avoids downloading 100MB assets.
- **Embedding in tests:** The test dump includes pre-computed embeddings so tests don't need the nomic model downloaded.
