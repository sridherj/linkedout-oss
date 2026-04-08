# Decision: Queue Strategy (Spike 0F)

**Date:** 2026-04-07
**Status:** Approved by SJ (2026-04-07)
**Deciders:** SJ

---

## Question

Is the Procrastinate task queue needed for a single-user OSS tool? Can enrichment and other async operations run synchronously? What breaks if Procrastinate is removed?

## Decision

**Remove Procrastinate. Run enrichment synchronously in the CLI/API call path.**

## Context

LinkedOut OSS is a single-user, self-hosted tool. There is no concurrent load — the user runs operations via CLI skills or the API. The original Procrastinate integration served a multi-user SaaS scenario where:

- Multiple users could trigger enrichment simultaneously
- A background worker pool processed jobs without blocking API responses
- Retry/DLQ semantics mattered for unattended operation at scale

None of these conditions apply to the OSS single-user use case.

## Current Procrastinate Footprint

### Files touched (15 total)

| File | Role |
|------|------|
| `backend/requirements.txt` | `procrastinate` dependency |
| `backend/src/shared/queue/config.py` | App + connector setup (async + sync), DB pool config |
| `backend/src/shared/queue/tasks.py` | 3 POC/spike tasks (`dummy_task`, `failing_task`, `concurrency_task`) |
| `backend/src/shared/queue/__init__.py` | Package docstring only |
| `backend/src/shared/queue/poc_test.py` | Manual POC test script |
| `backend/src/linkedout/enrichment_pipeline/tasks.py` | `enrich_profile` task — the only production task |
| `backend/src/linkedout/enrichment_pipeline/controller.py` | `_defer_enrichment_task()` enqueues via `sync_app` |
| `backend/src/linkedout/enrichment_pipeline/post_enrichment.py` | Docstring mentions Procrastinate (no import) |
| `backend/main.py` | Lifespan: opens async/sync connectors, starts worker task, shuts down |
| `backend/migrations/env.py` | Excludes `procrastinate_*` tables from Alembic autogenerate |
| `backend/tests/unit/enrichment_pipeline/test_enrich_task.py` | Unit tests for `enrich_profile` task |
| `backend/docs/plan/voyager-enrich-endpoint.md` | Planning doc reference |
| `backend/docs/specs/linkedout_enrichment_pipeline.collab.md` | Spec reference |
| `backend/docs/execution/phase3/sub-phase-2-import-pipeline.ai.md` | Execution doc |
| `backend/docs/execution/phase3/sub-phase-3-enrichment-pipeline.ai.md` | Execution doc |

### Production tasks (only 1)

| Task | Called from | What it does |
|------|-----------|-------------|
| `enrich_profile` | `controller.py:_defer_enrichment_task()` | Calls Apify API, then delegates to `PostEnrichmentService.process_enrichment_result()` |

The other 3 tasks (`dummy_task`, `failing_task`, `concurrency_task`) are POC spike artifacts with no production callers.

### Infrastructure overhead

- **4 PostgreSQL tables** created by `procrastinate schema --apply`: `procrastinate_jobs`, `procrastinate_events`, `procrastinate_periodic_defers`, `procrastinate_workers`
- **Async worker** started in `main.py` lifespan (asyncio task)
- **Two connection pools** (async + sync) managed separately from SQLAlchemy
- **psycopg3 dependency** (`psycopg` + `psycopg_pool`) — separate from the `psycopg2-binary` used by SQLAlchemy

## Analysis: What Happens If Removed

### Enrichment flow today
```
API request → create enrichment_event(queued) → defer to Procrastinate
  ... later, worker picks up ...
Worker → call Apify → PostEnrichmentService.process_enrichment_result() → done
```

### Enrichment flow after removal
```
API/CLI request → create enrichment_event(queued) → call Apify inline → PostEnrichmentService → done
```

### What breaks?
**Nothing meaningful.**

1. **No concurrent enrichment** — Single user won't trigger overlapping enrichments. If enriching N profiles, they process sequentially. This is actually *desirable* for a single-user tool: deterministic, debuggable, no race conditions.

2. **Blocking API response** — The `/enrich` endpoint currently returns immediately after queueing. With sync execution, it blocks until Apify returns (~3-5s per profile). For the OSS CLI-first model, this is fine — the CLI can show a progress bar. For the API, the endpoint can process profiles one-by-one in a loop with streaming progress (SSE) or just return after completion.

3. **Retry semantics** — Procrastinate provides `retry=3` on the task. Replace with a simple retry loop in the enrichment function (`tenacity` or manual, 3 attempts with backoff). This is simpler and more debuggable.

4. **Race condition guard in PostEnrichmentService** — The `process_enrichment_result()` method has a race condition re-check (lines 69-87) for when multiple workers process the same profile. With synchronous single-user execution, this guard is unnecessary but harmless — can keep or simplify later.

### What we gain

| Benefit | Detail |
|---------|--------|
| **Simpler setup** | No Procrastinate schema apply step, no worker management, no psycopg3 pool |
| **Fewer dependencies** | Remove `procrastinate`, `psycopg`, `psycopg_pool` from requirements |
| **Simpler main.py** | Remove ~20 lines of worker lifecycle management |
| **Debuggability** | Enrichment errors surface immediately in the CLI, not in a separate worker log |
| **No extra DB tables** | 4 fewer PostgreSQL tables to manage |
| **Simpler testing** | No need to mock queue infrastructure |

## Alternatives Considered

### 1. Keep Procrastinate (status quo)
- **Pro:** Already works, provides background processing
- **Con:** Massive overhead for single-user: extra dependency, extra DB tables, separate worker process, two connection pools, harder to debug, harder onboarding (user must run `procrastinate schema --apply`)
- **Verdict:** Rejected — complexity not justified for single-user

### 2. Replace with subprocess/asyncio background task
- **Pro:** Non-blocking enrichment without full queue infrastructure
- **Con:** Still adds complexity for minimal benefit. Single user doesn't need non-blocking — they're waiting for results anyway.
- **Verdict:** Rejected for now. Could revisit if users report enrichment of 100+ profiles being too slow synchronously. Even then, simple `asyncio.gather` or `concurrent.futures.ThreadPoolExecutor` would suffice without a queue.

### 3. Replace with simpler queue (e.g., in-memory, SQLite)
- **Pro:** Lighter than Procrastinate
- **Con:** Still unnecessary infrastructure for single-user sequential operations
- **Verdict:** Rejected — solving a problem that doesn't exist

### 4. Remove Procrastinate, run synchronously (chosen)
- **Pro:** Simplest possible implementation. Zero infrastructure. Easy to debug. Fast onboarding.
- **Con:** Enrichment blocks the caller. Mitigated by: CLI progress bars, sequential processing is actually desirable for single user.
- **Verdict:** Accepted

## Implementation Plan

### Step 1: Inline enrichment in controller
Replace `_defer_enrichment_task()` with direct call to the enrichment logic (Apify call + `PostEnrichmentService`). Add simple retry (3 attempts, exponential backoff).

### Step 2: Remove queue infrastructure
- Delete `backend/src/shared/queue/` directory entirely
- Remove `procrastinate`, `psycopg`, `psycopg_pool` from `requirements.txt`
- Remove worker lifecycle code from `main.py` lifespan (~20 lines)
- Remove `procrastinate_*` exclusion from `migrations/env.py`

### Step 3: Update enrichment task
- Move the core logic from `enrichment_pipeline/tasks.py` (the Apify call + PostEnrichmentService delegation) into a plain function in `enrichment_pipeline/service.py` or inline in the controller
- Delete `enrichment_pipeline/tasks.py`

### Step 4: Update tests
- Simplify `test_enrich_task.py` — test the enrichment function directly, no queue mocking needed
- Remove any queue-specific test fixtures

### Step 5: Update docs
- Remove Procrastinate references from specs and execution docs
- Update enrichment pipeline spec to reflect synchronous flow

### Step 6: Database cleanup (migration)
- Add Alembic migration to drop `procrastinate_*` tables (for users upgrading from queue-based version)
- Or document manual cleanup: `DROP TABLE IF EXISTS procrastinate_jobs, procrastinate_events, procrastinate_periodic_defers, procrastinate_workers CASCADE;`

## Future Considerations

If LinkedOut OSS ever supports batch enrichment of very large sets (1000+ profiles), consider adding a simple progress-reporting pattern:
- Process profiles in a loop
- Emit progress events (SSE or log lines) per profile
- CLI skill shows real-time progress bar
- No queue needed — just a loop with progress reporting

This is strictly a future concern and should not influence the current decision.

## Extension Error Handling Note

When the Chrome extension triggers enrichment via the API and it blocks/fails:
- Extension waits for the synchronous response (3-5s per profile)
- On failure, the extension logs the error to `~/linkedout-data/logs/extension.log` (via the backend API writing to the shared log directory)
- All extension-related errors (enrichment failures, API timeouts, rate limit events, Voyager API errors) go to the same `~/linkedout-data/logs/` structure — no separate error storage in `browser.storage.local` or console-only logging
- The existing extension activity log (200-entry ring buffer in `browser.storage.local`) is kept for the extension popup UI, but is NOT the source of truth for debugging — `~/linkedout-data/logs/` is
