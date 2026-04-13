# SP2: Core Pipeline

**Depends on:** SP1 (poll_run_safe, max_batch_size setting)
**Produces:** New file `bulk_enrichment.py` — the core batched enrichment pipeline
**Estimated scope:** ~400 lines of production code

## Overview

Create the central `bulk_enrichment.py` module that implements the full batch enrichment pipeline: state file management, lock file, chunking, dispatch → poll → fetch → persist → process loop, resume logic, and key rotation wiring.

This module is the heart of the system. SP3 wires it into the CLI and post-processing; SP4 tests it exhaustively.

---

## New File: `backend/src/linkedout/enrichment_pipeline/bulk_enrichment.py`

### Module-Level Design

The module exposes one main entry point:

```python
def enrich_profiles(
    profiles: list[tuple[str, str]],  # list of (profile_id, linkedin_url)
    db_session_factory,               # callable that yields a write session (context manager)
    post_enrichment_factory,          # callable(session) -> PostEnrichmentService
    embedding_provider: EmbeddingProvider | None = None,
    key_tracker: KeyHealthTracker | None = None,
    data_dir: str | Path | None = None,
    skip_embeddings: bool = False,
    on_progress: Callable | None = None,  # callback(enriched, failed, total, batch_idx)
) -> EnrichmentResult:
```

Caller passes everything needed — the pipeline doesn't reach into global state. This makes testing straightforward (inject fakes for everything).

### Data Types

```python
@dataclass
class EnrichmentResult:
    """Summary of a pipeline run."""
    total_profiles: int
    enriched: int
    failed: int
    batches_completed: int
    batches_total: int
    stopped_reason: str | None = None  # "all_keys_exhausted", "interrupted", None

@dataclass
class BatchState:
    """Reconstructed state of a single batch from the state file."""
    batch_idx: int
    urls: list[str]
    run_id: str | None = None
    dataset_id: str | None = None
    run_status: str | None = None
    result_count: int | None = None
    processed_urls: set[str] = field(default_factory=set)
    completed: bool = False
```

### State File Management

**Location:** `{data_dir}/enrichment/enrich-state.jsonl`

The state file is append-only JSONL. Each line is a JSON object with a `type` field.

#### Event Types

```jsonl
{"type":"batch_started","batch_idx":0,"run_id":"abc123","urls":["url1",...],"started_at":"2026-04-13T..."}
{"type":"batch_fetched","batch_idx":0,"run_id":"abc123","dataset_id":"def456","run_status":"SUCCEEDED","result_count":48}
{"type":"profile_processed","batch_idx":0,"linkedin_url":"url1","profile_id":"cp_xxx","status":"enriched"}
{"type":"profile_processed","batch_idx":0,"linkedin_url":"url2","profile_id":"cp_yyy","status":"failed","error":"..."}
{"type":"batch_completed","batch_idx":0,"enriched":48,"failed":2}
```

#### State File Functions

```python
def _load_state(state_path: Path) -> dict[int, BatchState]:
    """Read state file, reconstruct batch states. Returns {batch_idx: BatchState}."""

def _append_state(state_path: Path, event: dict) -> None:
    """Append a single event to the state file."""
```

`_load_state()` reads all lines, builds `BatchState` objects:
- `batch_started` → creates BatchState with `run_id`, `urls`
- `batch_fetched` → sets `dataset_id`, `run_status`, `result_count`
- `profile_processed` → adds URL to `processed_urls`
- `batch_completed` → sets `completed = True`

`_append_state()` opens file in append mode, writes one JSON line, flushes.

### Lock File

**Location:** `{data_dir}/enrichment/enrich.lock`

```python
@contextmanager
def _acquire_lock(data_dir: Path):
    """Acquire enrichment lock file. Raises SystemExit if already running."""
```

Lock file contains JSON: `{"pid": 12345, "started_at": "2026-04-13T..."}`

Logic:
1. If lock exists, read PID and timestamp
2. If PID is alive (`os.kill(pid, 0)` succeeds) → raise `SystemExit("enrichment already running (PID {pid})")`
3. If PID is dead → stale lock, reclaim (overwrite)
4. If timestamp is older than 6 hours → stale regardless of PID (guards PID reuse), reclaim
5. On exit (context manager `__exit__` + `atexit`): remove lock file
6. On exception: also remove lock file (finally block in context manager)

### Chunking

```python
def _chunk_profiles(
    profiles: list[tuple[str, str]],
    batch_size: int,
) -> list[list[tuple[str, str]]]:
    """Split profiles into batches of batch_size."""
```

Simple list slicing. Uses `max_batch_size` from `EnrichmentConfig` (default 100).

### Main Pipeline Loop

```python
def enrich_profiles(...) -> EnrichmentResult:
```

Pseudocode:

```
1. Resolve data_dir from settings if None
2. Create enrichment directory: {data_dir}/enrichment/
3. Create results directory: {data_dir}/enrichment/results/
4. Acquire lock file
5. Load state file (if exists) → existing_state
6. Chunk profiles into batches (max_batch_size)

7. For each batch (batch_idx, batch_profiles):
   a. Check existing_state for this batch_idx
   
   b. If batch_completed in state → skip entirely, increment counters
   
   c. If batch_fetched but not all profiles processed:
      - Re-read results from disk: results/{run_id}.json
      - Skip already-processed URLs (from state)
      - Process remaining profiles (see step 7g)
   
   d. If batch_started but not fetched:
      - Resume polling with saved run_id (poll_run_safe)
      - Go to step 7f
   
   e. If not started:
      - Get fresh API key: key_tracker.next_key() (or get_platform_apify_key())
      - Create new LinkedOutApifyClient(api_key)
      - Call client.enrich_profiles_async(batch_urls)
      - Append batch_started event to state file
      - Handle API errors:
        - 402 → tracker.mark_exhausted(key), retry with next key
        - 401/403 → tracker.mark_invalid(key), retry with next key
        - 429 → exponential backoff, retry same key
        - AllKeysExhaustedError → stop pipeline, report progress
   
   f. Poll + Fetch:
      - Call client.poll_run_safe(run_id)
      - Returns (status, dataset_id)
      - Call client.fetch_results(dataset_id)
      - Save to disk: results/{run_id}.json (R1: persist before any DB work)
      - Append batch_fetched event to state file
   
   g. Process results:
      - Match results to input URLs (join on linkedinUrl field)
      - For each profile in batch:
        - Skip if already in processed_urls (from state)
        - If result exists: call process_single_profile() (delegates to PostEnrichmentService)
        - If result missing: log as failed
        - Append profile_processed event to state file
      - After all profiles: batch embedding (if not skip_embeddings)
      - Append batch_completed event to state file
   
   h. Call on_progress callback (if provided)

8. Release lock file
9. Return EnrichmentResult
```

### Single Profile Processing

The pipeline delegates per-profile DB work to a callback passed in by SP3. In SP2, the pipeline module defines the processing interface but the actual `PostEnrichmentService` wiring happens in SP3's `process_batch()`.

For SP2, implement the core loop that:
1. Matches Apify results to input URLs via `linkedinUrl` field
2. Tracks which profiles succeeded vs failed (missing from results)
3. Writes `profile_processed` state events
4. Collects embedding texts for batch embedding (deferred to SP3's process_batch)

### Result Matching

```python
def _match_results(
    batch_urls: list[str],
    apify_results: list[dict],
) -> tuple[dict[str, dict], list[str]]:
    """Match Apify results to input URLs.
    
    Returns:
        (matched: {linkedin_url: apify_data}, missing: [urls not in results])
    
    Handles:
        - Case-insensitive URL matching
        - Duplicate linkedinUrl in results (first wins)
        - Extra results not in input (ignored)
    """
```

### Raw Result Persistence

```python
def _save_results(results_dir: Path, run_id: str, results: list[dict]) -> Path:
    """Save raw Apify dataset to disk. Returns the file path.
    
    CRITICAL: This must happen BEFORE any DB processing (R1).
    """
```

Writes to `{data_dir}/enrichment/results/{run_id}.json` as a JSON array.

### Key Rotation Wiring

Create a **new `LinkedOutApifyClient` per batch** with the key from `tracker.next_key()`.

Error handling in the batch dispatch loop:
- Wrap `enrich_profiles_async()` call in try/except
- **`ApifyCreditExhaustedError` (402)** → `tracker.mark_exhausted(key)`, get next key, retry
- **`ApifyAuthError` (401/403)** → `tracker.mark_invalid(key)`, get next key, retry
- **`ApifyRateLimitError` (429)** → exponential backoff (2s, 4s, 8s, max 3 retries), retry same key
- **`AllKeysExhaustedError`** → set `stopped_reason = "all_keys_exhausted"`, break out of batch loop

### Error Handling for Fetch

- `requests.Timeout` during `fetch_results()` → do NOT write `batch_fetched` to state. The state file only has `batch_started`, so resume will re-poll (gets terminal status again) and retry fetch.
- `requests.RequestException` → same treatment. No `batch_fetched` means resume retries from poll.

### Imports

```python
import atexit
import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from linkedout.enrichment_pipeline.apify_client import (
    AllKeysExhaustedError,
    ApifyAuthError,
    ApifyCreditExhaustedError,
    ApifyRateLimitError,
    KeyHealthTracker,
    LinkedOutApifyClient,
    get_platform_apify_key,
)
from shared.config import get_config
from shared.utilities.logger import get_logger
```

---

## Verification Checklist

After completing SP2:

1. Module imports cleanly: `python -c "from linkedout.enrichment_pipeline.bulk_enrichment import enrich_profiles"`
2. No circular imports
3. State file functions work in isolation (can be unit-tested with tmp_path)
4. Lock file acquire/release works
5. `_match_results()` handles all edge cases (duplicates, missing, extra)
6. The module does NOT import `PostEnrichmentService` directly — it receives processing callbacks
7. All existing tests still pass: `pytest backend/tests/unit/enrichment_pipeline/ -v`

Note: Full integration tests are in SP4. SP2 should have basic unit tests for:
- `_load_state()` / `_append_state()` with sample JSONL
- `_match_results()` edge cases
- `_chunk_profiles()` boundary conditions
- Lock file acquire/release/stale detection
