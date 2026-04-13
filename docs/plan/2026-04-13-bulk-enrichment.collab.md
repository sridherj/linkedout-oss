# Bulk Enrichment Pipeline

**Date:** 2026-04-13
**Status:** Draft
**Goal:** Replace one-at-a-time sync enrichment with batched async pipeline. Same code path for 1 profile (extension) or 5000 (CLI).

## Problem

The CLI (`linkedout enrich`) calls `enrich_profile_sync()` per profile — one HTTP round-trip to Apify's `run-sync-get-dataset-items` endpoint, blocking, 300s hard timeout. For thousands of profiles this is:
- Slow (serial, no parallelism)
- Fragile (crash = lost progress, no resume)
- Wasteful (N API calls instead of ~N/50)

The building blocks for batch already exist but aren't wired up:
- `enrich_profiles_async(urls)` starts an async run with multiple URLs
- `poll_run(run_id)` + `fetch_results(dataset_id)` retrieves results
- `EmbeddingProvider.embed(texts: list[str])` does batch embeddings
- `PostEnrichmentService.process_enrichment_result()` is per-profile and idempotent

## API Facts (Verified)

| Fact | Detail |
|------|--------|
| Async run | `POST /v2/acts/{actorId}/runs` — accepts N URLs in `queries`, Apify parallelizes internally |
| Sync endpoint | `run-sync-get-dataset-items` — 300s hard timeout, single-profile only |
| Result matching | Each dataset item has `linkedinUrl` field — no ordering guarantee |
| Partial results | Datasets are append-only. FAILED/ABORTED/TIMED-OUT runs still have partial data in `defaultDatasetId` |
| `defaultDatasetId` | Allocated at run creation, always present regardless of run status |
| Rate limits | 25–256 concurrent runs (plan-dependent); 250K req/min global |
| No batch API | No dedicated batch endpoint. Pattern is: start async run → poll → fetch dataset |

## Hard Requirements

### R1: Never Lose Paid Data
Every byte Apify returns must be persisted to disk before any other processing. If the process crashes, the data is recoverable from `results/{run_id}.json`. This applies to:
- **Successful runs** — full dataset saved before DB writes
- **Failed/aborted/timed-out runs** — partial dataset still fetched and saved (Apify charges per profile scraped, not per successful run)
- **The `defaultDatasetId` is always present** on the run object regardless of status — we must always attempt to fetch it

**Invariant:** If Apify charged us for a profile, we have the raw data on disk.

### R2: Crash Recovery at Any Point
The pipeline must be resumable after a crash at any stage:
- **Crash before Apify call** — no state written, restart is a fresh run
- **Crash during polling** — state file has `batch_started` with `run_id`; resume polls the existing run (Apify run continues server-side regardless of client)
- **Crash after fetch, before DB writes** — results on disk in `results/{run_id}.json`; state file has `batch_fetched`; resume re-reads from disk and processes
- **Crash during DB writes** — state file tracks per-profile `profile_processed` events; resume skips already-processed profiles, processes remaining from disk
- **Crash during embedding** — DB writes already committed; embeddings can be regenerated from DB data (or via `linkedout embed`)

**Invariant:** No crash scenario requires re-calling Apify for data we already received.

### R3: Idempotency
Re-running the pipeline (or resuming after crash) must not produce duplicates or corrupt data:
- **Apify dispatch** — state file tracks which batches were submitted; don't re-submit
- **DB writes** — `PostEnrichmentService` does race-condition re-check; `ProfileEnrichmentService.enrich()` does delete+insert (not insert-only)
- **Query filter** — only selects `has_enriched_data = false`; already-enriched profiles are skipped
- **State file** — tracks per-profile processing status; resume skips completed profiles

**Invariant:** Running `linkedout enrich` twice with the same data produces the same DB state as running it once.

## Design

### Core Principle: One Batched Pipeline

The caller passes a list of profiles. Could be 1 (Chrome extension enrichment), could be 5000 (CLI `linkedout enrich`). The pipeline handles chunking, dispatch, and processing internally. No separate "bulk" vs "single" code paths.

### MAX_BATCH_SIZE

Internal constant: 100. Caps how many URLs go into a single Apify run. Reasons:
- Actor timeout risk on huge inputs
- Smaller batches = faster partial results = better recovery granularity
- Failed batch loses at most MAX_BATCH_SIZE profiles' worth of Apify credits

Not user-configurable. Just a sensible internal cap.

### Pipeline Stages

```
Input: list of (profile_id, linkedin_url)
                    │
                    ▼
        ┌─── Chunk into batches ───┐
        │   (MAX_BATCH_SIZE each)  │
        └──────────┬───────────────┘
                   │
        ┌──────────▼───────────────┐
Stage 1 │  Apify Async Run         │  POST /runs with batch URLs
        │  → run_id                │  Log batch_started to state file
        └──────────┬───────────────┘
                   │
        ┌──────────▼───────────────┐
Stage 2 │  Poll for Completion     │  GET /actor-runs/{runId}
        │  → dataset_id           │  Handles SUCCEEDED + FAILED/ABORTED/TIMED-OUT
        └──────────┬───────────────┘
                   │
        ┌──────────▼───────────────┐
Stage 3 │  Fetch + Persist Raw     │  GET /datasets/{id}/items
        │  → results/{run_id}.json │  Save to disk BEFORE any DB work
        └──────────┬───────────────┘
                   │
        ┌──────────▼───────────────┐
Stage 4 │  Match Results to Input  │  Join on linkedinUrl
        │  Identify missing URLs   │  (URLs in input but not in results = failed)
        └──────────┬───────────────┘
                   │
        ┌──────────▼───────────────┐
Stage 5 │  Post-Process Batch      │  Per-profile: DB writes (profile, exp, edu, skills)
        │  (DB writes)             │  Batch: embeddings via embed(texts)
        │  (Batch embeddings)      │  Archive to JSONL
        │  (JSONL archive)         │  Log profile_processed to state file
        └──────────┬───────────────┘
                   │
              Log batch_completed
              Next batch →
```

### Stage 5 Detail: Batched Post-Processing

Currently `ProfileEnrichmentService.enrich()` calls `embed_single()` per profile. The batch pipeline should:

1. **DB writes** — still per-profile (each profile's experience/education/skills are delete+insert, needs individual transaction boundary for idempotency). Loop within a single session, flushing per profile. `ProfileEnrichmentService.enrich()` is called with `embedding_provider=None` during this phase — embedding is deferred to step 2.
2. **Batch embedding** — after all DB writes for the batch succeed, collect `build_embedding_text()` outputs for all profiles, call `embed(texts)` once, then assign vectors back. One API call per batch instead of N. Default behavior; skippable via `--skip-embeddings` for deferral to `linkedout embed`. **Note: this is a behavior change** — the current CLI passes `embedding_provider=None` and defers all embedding to `linkedout embed`. The new default aligns CLI with the HTTP controller (extension) flow, which already does inline embedding.
3. **JSONL archive** — batch-append all results in one file open/write/close cycle.
4. **Search vector** — computed per-profile during DB writes (cheap, in-memory string concat).

### State File for Crash Recovery

**Location:** `{data_dir}/enrichment/enrich-state.jsonl`

Append-only JSONL. Each line is a state event:

```jsonl
{"type":"batch_started","batch_idx":0,"run_id":"abc123","urls":["url1",...],"started_at":"2026-04-13T..."}
{"type":"batch_fetched","batch_idx":0,"run_id":"abc123","dataset_id":"def456","run_status":"SUCCEEDED","result_count":48}
{"type":"profile_processed","batch_idx":0,"linkedin_url":"url1","profile_id":"cp_xxx","status":"enriched"}
{"type":"profile_processed","batch_idx":0,"linkedin_url":"url2","profile_id":"cp_yyy","status":"failed","error":"..."}
{"type":"batch_completed","batch_idx":0,"enriched":48,"failed":2}
```

**Resume logic** (automatic — no `--resume` flag needed, matching `linkedout embed` pattern):
1. Read state file if it exists, reconstruct batch states
2. **batch_completed** → skip entirely
3. **batch_fetched but not all profiles processed** → re-read `results/{run_id}.json`, process remaining profiles
4. **batch_started but not fetched** → resume polling with saved `run_id`, then fetch + process
5. **Not started** → start fresh
6. **No state file** → fresh run

### Concurrency Protection

**Lock file:** `{data_dir}/enrichment/enrich.lock`

On pipeline start, create a lock file containing the PID and timestamp. Before creating, check for an existing lock:
1. If lock exists, read PID — if process is alive (`os.kill(pid, 0)`), exit with "enrichment already running (PID {pid})"
2. If PID is dead → stale lock from crash, reclaim it
3. If lock is older than 6 hours → treat as stale regardless (guards against PID reuse)
4. On clean exit or unhandled exception, remove the lock file (`atexit` + context manager)

### Key Rotation Wiring

Create a **new `LinkedOutApifyClient` per batch** with the key from `tracker.next_key()`. No mutable state on the client.

Wire up error handling in the batch dispatch loop:
- **402** → `tracker.mark_exhausted(key)`, retry with `next_key()`
- **401/403** → `tracker.mark_invalid(key)`, retry with `next_key()`
- **429** → exponential backoff, retry same key
- **`AllKeysExhaustedError`** → stop pipeline, report progress so far

These `mark_*` methods exist on `KeyHealthTracker` today but are never called — this plan wires them up.

### Raw Result Persistence

**Location:** `{data_dir}/enrichment/results/{run_id}.json`

Full Apify dataset response saved to disk before any DB processing. This means:
- Crash during DB writes → re-read from disk, no Apify re-call
- Data survives DB wipes
- Easy to inspect/debug
- Complements existing `apify-responses.jsonl` (which archives per-profile after processing)

### Partial Results on Failed Runs

Current `poll_run()` raises `RuntimeError` on FAILED/ABORTED/TIMED-OUT and discards the `defaultDatasetId`. Fix:

- **New method `poll_run_safe()`** — returns `(status, dataset_id)` tuple. Always returns `dataset_id` regardless of run status. Existing `poll_run()` unchanged (no contract break).
- Caller fetches dataset regardless of status
- Missing URLs (in input but not in results) logged as failed
- State file records `run_status` so we know it was partial

### Error Handling Summary

| Failure | Behavior |
|---------|----------|
| Ctrl+C mid-polling | State file has `batch_started`; resume picks up polling |
| Ctrl+C during DB processing | State file tracks per-profile progress; resume skips done profiles |
| Apify run FAILED/ABORTED/TIMED-OUT | Fetch partial results from dataset (R1), process what we got, log missing as failed |
| Some profiles missing from results | Log as failed in state file, continue to next batch |
| DB write crash mid-batch | Results on disk (R1); resume re-reads and processes remaining (R2) |
| 402 (credits exhausted) | Key rotation marks key exhausted; if all keys exhausted, stop with progress report |
| 429 (rate limit) | Exponential backoff on batch start, retry |
| 401/403 (bad key) | Key rotation marks key invalid, retry with next key |
| Embedding API failure | DB writes already committed; log to `failed_embeddings.jsonl`; `linkedout embed` can backfill |

## Changes

| File | Change |
|------|--------|
| **New:** `enrichment_pipeline/bulk_enrichment.py` | Core pipeline: chunk → dispatch → poll → fetch → process. State file management. Resume logic. |
| `enrichment_pipeline/apify_client.py` | Add `poll_run_safe()` returning `(status, dataset_id)` — always returns dataset_id regardless of run status. Existing `poll_run()` unchanged. |
| `enrichment_pipeline/post_enrichment.py` | Add `process_batch()` that processes N results, collects embedding texts, calls `embed()` once, batch-archives to JSONL. Delegates per-profile DB writes to existing `process_enrichment_result()`. |
| `commands/enrich.py` | Rewrite to call `bulk_enrichment.enrich_profiles(profiles)`. Keep `--dry-run`, `--limit`, progress reporting. Auto-resume from state file (no `--resume` flag). Add `--skip-embeddings`. |
| `shared/config/settings.py` | Add `max_batch_size: int = 100`, `skip_embeddings: bool = False` to `EnrichmentConfig` |
| `shared/utils/apify_archive.py` | Add `append_apify_archive_batch()` for writing multiple entries in one I/O cycle |

### What Stays the Same

- `PostEnrichmentService.process_enrichment_result()` — per-profile logic unchanged
- `ProfileEnrichmentService.enrich()` — per-profile DB writes unchanged
- Key rotation (`KeyHealthTracker`) — works as-is, get fresh key per batch
- `--dry-run` — same behavior
- HTTP controller — still uses sync path for single-profile enrichment (extension flow). Already does inline embedding; no change needed.

## Test Plan

All tests mock Apify HTTP calls (no real API calls). Tests use a `tmp_path` fixture for state files and result storage.

### Test Infrastructure

- **`FakeApify`**: A mock class that simulates the Apify async run lifecycle. Configurable per-test:
  - `start_run(urls) → run_id` — records the input, returns fake run_id
  - `poll(run_id) → (status, dataset_id)` — returns configurable status (SUCCEEDED, FAILED, ABORTED, TIMED-OUT) after N polls
  - `fetch(dataset_id) → list[dict]` — returns configurable results, can omit specific URLs to simulate partial scraping
  - Can be configured to raise specific HTTP errors (402, 429, 401) on specific calls
- **`FakeEmbeddingProvider`**: Already exists in test suite. Returns deterministic vectors.
- **State file helpers**: Read state JSONL back into structured data for assertions.

### Recovery Tests (R1 + R2)

These are the critical tests. Each simulates a crash at a specific pipeline stage and verifies recovery.

#### T1: Crash after Apify run started, before poll completes
- Setup: Start pipeline with 1 batch of 5 URLs. FakeApify returns run_id. Inject crash (exception) during polling.
- State file should contain `batch_started` with `run_id`.
- Resume: Pipeline reads state, re-polls same `run_id`, fetches results, processes all 5.
- Assert: All 5 profiles enriched. No duplicate Apify calls (start_run called once total across both runs).

#### T2: Crash after fetch, before any DB writes
- Setup: 1 batch of 5 URLs. FakeApify succeeds. Results saved to `results/{run_id}.json`. Inject crash before DB processing.
- State file should contain `batch_fetched`.
- Resume: Pipeline re-reads from `results/{run_id}.json`, processes all 5.
- Assert: `results/{run_id}.json` exists and is complete. All 5 profiles enriched. Apify never re-called.

#### T3: Crash mid-DB-processing (3 of 5 profiles done)
- Setup: 1 batch of 5 URLs. FakeApify succeeds. Process 3 profiles, inject crash on 4th.
- State file should have 3 `profile_processed` events.
- Resume: Pipeline re-reads results from disk, skips 3 done profiles, processes remaining 2.
- Assert: All 5 profiles enriched. Profiles 1-3 processed exactly once (not re-processed).

#### T4: Apify run FAILED — partial results recovered
- Setup: 1 batch of 5 URLs. FakeApify returns FAILED status after polling. Dataset contains 3 of 5 results.
- Assert: `results/{run_id}.json` saved with 3 results. 3 profiles enriched. 2 logged as failed (missing from results). State file records `run_status: "FAILED"`.

#### T5: Apify run TIMED-OUT — partial results recovered
- Same as T4 but with TIMED-OUT status. Verifies we don't treat timeout differently from failure.

#### T6: Apify run ABORTED (e.g., user cancelled in Apify console)
- Same pattern. Dataset may have 0 results. Assert: 0 enriched, all 5 failed, no crash, state file is consistent.

#### T7: Multi-batch crash — first batch done, crash during second
- Setup: 10 URLs, MAX_BATCH_SIZE=5, so 2 batches. Batch 0 completes fully. Crash during batch 1 polling.
- Resume: Batch 0 skipped (state shows `batch_completed`). Batch 1 resumed from `batch_started`.
- Assert: All 10 profiles enriched after resume. Batch 0 profiles not re-processed.

### Never-Lose-Paid-Data Tests (R1)

#### T8: Results saved to disk before DB processing
- Setup: 1 batch of 3 URLs. FakeApify succeeds. Mock DB to raise on first write.
- Assert: `results/{run_id}.json` exists with all 3 results. DB has 0 enriched profiles. Data is not lost.

#### T9: Partial results from failed run saved to disk
- Setup: FakeApify returns FAILED, dataset has 2 of 5 results.
- Assert: `results/{run_id}.json` has exactly 2 items. Both are processable on resume.

#### T10: Results file is valid JSON and contains all Apify fields
- Setup: FakeApify returns realistic response (use sample from `docs/reference/apify_sample_response.json`).
- Assert: File round-trips through `json.load()`. Contains `linkedinUrl`, `firstName`, `experience`, etc.

### Idempotency Tests (R3)

#### T11: Full pipeline run twice — same result
- Setup: Run pipeline for 5 profiles. Run it again (same profiles, but now `has_enriched_data=true`).
- Assert: Second run enriches 0 profiles (query filter skips them). DB state identical after both runs.

#### T12: Resume processes each profile exactly once
- Setup: T3 scenario (crash mid-batch). Verify via mock call counts that `process_enrichment_result` is called exactly 5 times total (3 before crash + 2 on resume), never re-called for the first 3.

#### T13: State file prevents re-submission of batches
- Setup: 2 batches. Both complete. Run pipeline again with `--resume` and existing state file.
- Assert: `start_run` never called (both batches already completed in state).

### Batch Embedding Tests

#### T14: Batch embedding called once per Apify batch
- Setup: 1 batch of 5 URLs. FakeEmbeddingProvider tracks calls.
- Assert: `embed(texts)` called once with list of 5 texts. `embed_single` never called.

#### T15: --skip-embeddings defers embedding
- Setup: Same as T14 but with `skip_embeddings=True`.
- Assert: `embed()` never called. Profiles have no embedding vectors. `linkedout embed` can backfill.

#### T16: Embedding failure doesn't lose DB writes
- Setup: 1 batch of 3 URLs. DB writes succeed. Embedding provider raises exception.
- Assert: All 3 profiles have `has_enriched_data=true`, experiences, education, skills in DB. Embeddings are null. Failed embeddings logged to JSONL.

### Key Rotation / API Error Tests

#### T17: 402 on batch start — rotate key, retry
- Setup: 2 keys. First key returns 402 on `start_run`. Second key succeeds.
- Assert: Batch completes. First key marked exhausted. Second key used.

#### T18: All keys exhausted — stop gracefully with progress report
- Setup: 2 batches, 1 key. First batch succeeds. Key returns 402 on second batch start.
- Assert: First batch fully processed. Second batch not started. Summary reports 1 batch done, 1 failed.

#### T19: 429 — exponential backoff and retry
- Setup: First `start_run` returns 429. Second attempt (after backoff) succeeds.
- Assert: Batch completes. Backoff delay observed (mock `time.sleep`).

### Edge Cases

#### T20: Empty input list — no-op
- Assert: No Apify calls, no state file created, clean exit.

#### T21: Single profile (batch_size=1 effectively)
- Assert: Works identically to batch flow. One Apify run with 1 URL.

#### T22: All profiles missing from Apify results (dataset empty)
- Setup: FakeApify SUCCEEDED but returns empty dataset.
- Assert: All profiles logged as failed. No crash. State file consistent.

#### T23: Result URL doesn't match any input URL (Apify returned unexpected profile)
- Assert: Extra result ignored. Input profiles without matching result logged as failed.

#### T24: Duplicate `linkedinUrl` in Apify results
- Assert: First result used, duplicate ignored. No double-processing.

#### T25: Concurrent run rejected by lock file
- Setup: Create a lock file with current PID (simulating a running process).
- Assert: Second pipeline invocation exits immediately with "enrichment already running" message. No state file changes.

#### T26: Stale lock file reclaimed
- Setup: Create a lock file with a dead PID (e.g., PID 999999).
- Assert: Pipeline reclaims the lock, runs normally.

#### T27: Lock file older than 6 hours reclaimed regardless of PID
- Setup: Create a lock file with current PID but timestamp 7 hours ago.
- Assert: Pipeline treats it as stale and reclaims.

#### T28: `fetch_results()` timeout during dataset download
- Setup: FakeApify SUCCEEDED but `fetch_results()` raises `requests.Timeout`.
- Assert: State file has `batch_started` (not `batch_fetched`). Resume re-polls (gets SUCCEEDED again), retries fetch.

## Resolved Questions

1. **MAX_BATCH_SIZE = 100**. Apify input limit is 500KB which fits hundreds of URLs. 100 balances recovery granularity vs overhead.
2. **Embeddings: inline by default.** Batch `embed(texts)` call at the end of each Apify batch. Configurable via `skip_embeddings: bool = False` in EnrichmentConfig (and `--skip-embeddings` CLI flag) for cases where you want to defer to `linkedout embed`. The HTTP controller (extension) flow already does inline embedding — this makes the CLI match. **Behavior change from current CLI** (which skips embeddings entirely).
3. **State file: keep.** Stored in `{data_dir}/enrichment/` for audit trail. No auto-cleanup.
4. **`poll_run_safe()` not `poll_run()` modification.** New method avoids breaking existing contract.
5. **Auto-resume, no `--resume` flag.** Matches `linkedout embed` pattern. State file presence triggers resume automatically.
6. **New client per batch for key rotation.** `tracker.next_key()` → fresh `LinkedOutApifyClient`. Wires up `mark_exhausted()` / `mark_invalid()` which exist but are uncalled today.
7. **Lock file with PID + 6h max age.** Prevents concurrent runs. PID check handles crash-left stale locks; 6h ceiling guards against PID reuse edge case.
