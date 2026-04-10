# Sub-Phase 3: Procrastinate Queue Removal

**Phase:** 6 — Code Cleanup for OSS
**Plan task:** 6C (Procrastinate Queue Removal)
**Dependencies:** sp1
**Blocks:** sp5, sp6, sp7, sp8
**Can run in parallel with:** sp2, sp4

## Objective
Remove the Procrastinate task queue entirely and inline enrichment as a synchronous operation with simple retry. Per `docs/decision/queue-strategy.md` (Phase 0F).

## Context
- Read shared context: `docs/execution/phase-06/_shared_context.md`
- Read plan (6C section): `docs/plan/phase-06-code-cleanup.md`
- Read decision: `docs/decision/queue-strategy.md` — implementation plan sections 1-6
- Read enrichment pipeline: `backend/src/linkedout/enrichment_pipeline/controller.py`
- Read enrichment tasks: `backend/src/linkedout/enrichment_pipeline/tasks.py`

## Deliverables

### 1. Delete Queue Module

Delete the entire directory:
- `backend/src/shared/queue/__init__.py`
- `backend/src/shared/queue/config.py`
- `backend/src/shared/queue/tasks.py` — 3 POC tasks (dummy_task, failing_task, concurrency_task)
- `backend/src/shared/queue/poc_test.py`
- The `backend/src/shared/queue/` directory itself

### 2. Remove Procrastinate from `backend/main.py`

- Remove the Procrastinate startup block (worker initialization, ~lines 93-105)
- Remove the Procrastinate shutdown block (worker cleanup, ~lines 119-126)
- Remove `asyncio` import if no longer needed elsewhere in the file
- Remove any `from shared.queue` imports

### 3. Inline Enrichment — Extract Core Logic

In `backend/src/linkedout/enrichment_pipeline/tasks.py`:
- Identify the core enrichment logic (Apify call → PostEnrichmentService)
- Extract it into a plain async/sync function

Create or update `backend/src/linkedout/enrichment_pipeline/service.py` (or inline in controller):
- The extracted function should take a profile ID (or relevant params) and run enrichment synchronously
- Add simple retry: 3 attempts, exponential backoff
  - Check if `tenacity` is already in requirements.txt — if yes, use it
  - If not, implement manual retry (sleep 1s, 2s, 4s)
- On final failure: log error, return failure result (don't crash)

### 4. Update Enrichment Controller

In `backend/src/linkedout/enrichment_pipeline/controller.py`:
- Replace `_defer_enrichment_task()` (which imports `sync_app` from Procrastinate) with a direct call to the extracted enrichment function
- Remove any `from shared.queue` imports
- Remove any Procrastinate-specific error handling

### 5. Delete `tasks.py` After Extraction

Once the core logic is extracted and the controller calls the new function directly:
- Delete `backend/src/linkedout/enrichment_pipeline/tasks.py`
- Or if `tasks.py` contains other non-queue logic, strip only the queue-related parts

### 6. Clean Up `migrations/env.py`

In `backend/migrations/env.py`:
- Remove the `procrastinate_*` table exclusion from autogenerate filtering
- This ensures Alembic autogenerate won't try to create/drop Procrastinate tables

### 7. Note: NO Migration or requirements.txt Changes Here

- Procrastinate tables will be handled by the fresh baseline migration in sp7
- `procrastinate`, `psycopg`, `psycopg_pool` removal from requirements.txt happens in sp8
- Do NOT create a separate Alembic migration for dropping Procrastinate tables
- Do NOT modify `requirements.txt` in this sub-phase

## Verification
1. `backend/src/shared/queue/` does not exist
2. `grep -rn "procrastinate" backend/src/ --include="*.py"` returns zero matches
3. `grep -rn "from shared.queue" backend/src/ --include="*.py"` returns zero matches
4. `grep -rn "sync_app" backend/src/ --include="*.py"` returns zero matches
5. `cd backend && uv run python -c "from main import app; print('main.py imports OK')"` succeeds
6. `cd backend && uv run python -c "from linkedout.enrichment_pipeline.controller import EnrichmentController; print('Controller imports OK')"` succeeds
7. `cd backend && uv run ruff check src/linkedout/enrichment_pipeline/` has no new errors

## Notes
- The enrichment pipeline's Apify integration may have external dependencies (API keys, etc.). The sync function should handle missing keys gracefully (log warning, skip enrichment).
- Keep `psycopg2-binary` — it's used by SQLAlchemy, not Procrastinate. The `psycopg` (async driver) and `psycopg_pool` are Procrastinate-specific — verified and removed in sp8.
- If `tenacity` is not in requirements.txt and you need it for retry, add it. Otherwise, use a simple manual retry loop.
