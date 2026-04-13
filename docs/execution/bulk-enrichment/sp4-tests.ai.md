# SP4: Tests

**Depends on:** SP1 + SP2 + SP3 (all production code must be in place)
**Produces:** Comprehensive test suite — 28 test cases (T1–T28) covering recovery, data safety, idempotency, embedding, key rotation, and edge cases
**Estimated scope:** ~800 lines of test code

## Overview

Build the `FakeApify` test infrastructure and implement all 28 test cases from the plan. These tests are the proof that R1 (never lose paid data), R2 (crash recovery), and R3 (idempotency) are satisfied.

---

## Test Infrastructure

### New File: `backend/tests/unit/enrichment_pipeline/test_bulk_enrichment.py`

All 28 tests go in this one file. Organize with pytest classes for grouping.

### FakeApify

A mock class that simulates the Apify async run lifecycle. Replaces `LinkedOutApifyClient` in tests.

```python
class FakeApify:
    """Mock Apify client for testing bulk enrichment pipeline.
    
    Configurable behaviors:
    - How many polls before reaching terminal state
    - Which terminal state to return (SUCCEEDED, FAILED, ABORTED, TIMED-OUT)
    - Which URLs appear in results (for testing partial scraping)
    - Which HTTP errors to raise on specific calls
    """
    
    def __init__(self):
        self.runs: dict[str, dict] = {}  # run_id -> {urls, status, dataset_id, results}
        self._run_counter = 0
        self._polls_before_done = 1  # How many polls return RUNNING before terminal
        self._terminal_status = "SUCCEEDED"
        self._missing_urls: set[str] = set()  # URLs to omit from results
        self._error_on_start: Exception | None = None  # Raise this on enrich_profiles_async
        self._error_on_fetch: Exception | None = None  # Raise this on fetch_results
        self._start_call_count = 0
        self._poll_call_count = 0
        self._fetch_call_count = 0
    
    def enrich_profiles_async(self, urls: list[str]) -> str:
        """Start a fake async run."""
        self._start_call_count += 1
        if self._error_on_start:
            raise self._error_on_start
        
        self._run_counter += 1
        run_id = f"fake_run_{self._run_counter}"
        dataset_id = f"fake_dataset_{self._run_counter}"
        
        # Build results: one dict per URL (minus missing_urls)
        results = []
        for url in urls:
            if url not in self._missing_urls:
                results.append(self._make_profile_result(url))
        
        self.runs[run_id] = {
            "urls": urls,
            "status": self._terminal_status,
            "dataset_id": dataset_id,
            "results": results,
            "_polls_remaining": self._polls_before_done,
        }
        return run_id
    
    def poll_run_safe(self, run_id: str, **kwargs) -> tuple[str, str]:
        """Poll a fake run. Returns (status, dataset_id)."""
        self._poll_call_count += 1
        run = self.runs[run_id]
        if run["_polls_remaining"] > 0:
            run["_polls_remaining"] -= 1
            # In real code this would be called in a loop
            # For testing, we fast-forward to done
        return (run["status"], run["dataset_id"])
    
    def fetch_results(self, dataset_id: str) -> list[dict]:
        """Fetch fake results."""
        self._fetch_call_count += 1
        if self._error_on_fetch:
            raise self._error_on_fetch
        
        for run in self.runs.values():
            if run["dataset_id"] == dataset_id:
                return run["results"]
        return []
    
    @staticmethod
    def _make_profile_result(linkedin_url: str) -> dict:
        """Generate a realistic-looking Apify result for a URL."""
        # Extract name from URL for deterministic test data
        slug = linkedin_url.rstrip("/").split("/")[-1]
        return {
            "linkedinUrl": linkedin_url,
            "publicIdentifier": slug,
            "firstName": f"First_{slug}",
            "lastName": f"Last_{slug}",
            "headline": f"Engineer at TestCo",
            "about": f"About {slug}",
            "location": {
                "linkedinText": "San Francisco, CA",
                "parsed": {"city": "San Francisco", "state": "CA", "country": "US"},
            },
            "experience": [
                {
                    "position": "Software Engineer",
                    "companyName": "TestCo",
                    "companyLinkedinUrl": "https://linkedin.com/company/testco",
                    "startDate": {"year": 2023, "month": 1},
                    "endDate": {"text": "Present"},
                }
            ],
            "education": [
                {
                    "schoolName": "Test University",
                    "degree": "BS",
                    "fieldOfStudy": "CS",
                    "startDate": {"year": 2019},
                    "endDate": {"year": 2023},
                }
            ],
            "skills": [{"name": "Python"}, {"name": "Testing"}],
            "topSkills": ["Architecture"],
            "connectionsCount": 500,
        }
```

### FakeEmbeddingProvider

Already exists in the test suite. If not available directly, create a minimal version:

```python
class FakeEmbeddingProvider:
    """Deterministic embedding provider for testing."""
    
    def __init__(self, dimension: int = 384):
        self._dimension = dimension
        self.embed_call_count = 0
        self.embed_single_call_count = 0
        self._should_fail = False
    
    def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_call_count += 1
        if self._should_fail:
            raise RuntimeError("Embedding failed")
        return [[0.1] * self._dimension for _ in texts]
    
    def embed_single(self, text: str) -> list[float]:
        self.embed_single_call_count += 1
        return [0.1] * self._dimension
    
    def model_name(self) -> str:
        return "fake-model"
    
    def dimension(self) -> int:
        return self._dimension
```

### State File Helpers

```python
def read_state_events(state_path: Path) -> list[dict]:
    """Read all events from a state JSONL file."""
    if not state_path.exists():
        return []
    events = []
    for line in state_path.read_text().splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events

def count_events(events: list[dict], event_type: str) -> int:
    """Count events of a specific type."""
    return sum(1 for e in events if e["type"] == event_type)
```

### Common Fixtures

```python
@pytest.fixture
def data_dir(tmp_path):
    """Temporary data directory for tests."""
    return tmp_path / "linkedout-data"

@pytest.fixture
def state_path(data_dir):
    """Path to enrichment state file."""
    return data_dir / "enrichment" / "enrich-state.jsonl"

@pytest.fixture
def results_dir(data_dir):
    """Path to enrichment results directory."""
    return data_dir / "enrichment" / "results"

@pytest.fixture
def fake_apify():
    """Fresh FakeApify instance."""
    return FakeApify()

@pytest.fixture
def sample_profiles():
    """5 sample (profile_id, linkedin_url) tuples."""
    return [
        (f"cp_{i}", f"https://linkedin.com/in/person-{i}")
        for i in range(5)
    ]
```

---

## Test Cases

### Recovery Tests (R1 + R2) — T1 through T7

#### T1: Crash after Apify run started, before poll completes

```python
class TestRecovery:
    def test_t1_crash_during_polling_resume_completes(self, data_dir, sample_profiles, fake_apify):
        """T1: Crash after Apify run started, before poll completes.
        
        Run 1: Start pipeline, inject crash during polling.
        State file has batch_started with run_id.
        Run 2: Resume — re-poll same run_id, fetch, process all 5.
        Assert: All 5 enriched. start_run called once total.
        """
```

Implementation approach:
- First run: Patch the pipeline to raise after `enrich_profiles_async()` succeeds and state writes `batch_started`, but before `poll_run_safe()` returns.
- Verify state file has `batch_started` event with `run_id`.
- Second run: Call `enrich_profiles()` again with same profiles and data_dir. Pipeline reads state, finds `batch_started`, resumes polling.
- Assert: `fake_apify._start_call_count == 1` (not re-submitted). All 5 profiles enriched.

#### T2: Crash after fetch, before any DB writes

```python
    def test_t2_crash_after_fetch_resume_from_disk(self, data_dir, sample_profiles, fake_apify):
        """T2: Results saved to disk, crash before DB writes.
        
        State has batch_fetched. results/{run_id}.json exists.
        Resume re-reads from disk, processes all 5.
        Assert: Apify never re-called. All 5 enriched.
        """
```

Implementation:
- First run: Let fetch succeed, state writes `batch_fetched`, results saved to disk. Crash before processing.
- Second run: Pipeline finds `batch_fetched` in state, reads results from disk, processes.
- Assert: `fake_apify._fetch_call_count == 1`. Results file exists.

#### T3: Crash mid-DB-processing (3 of 5 profiles done)

```python
    def test_t3_crash_mid_processing_resume_skips_done(self, data_dir, sample_profiles, fake_apify):
        """T3: 3 of 5 profiles processed, crash on 4th.
        
        State has 3 profile_processed events.
        Resume skips done profiles, processes remaining 2.
        Assert: All 5 enriched. First 3 processed exactly once.
        """
```

Implementation:
- First run: Patch `process_enrichment_result` to raise after 3 calls.
- State has 3 `profile_processed` events.
- Second run: Pipeline reads state, skips 3 done profiles, processes remaining 2.
- Assert: `process_enrichment_result` call count = 5 total (3 + 2, not 3 + 5).

#### T4: Apify run FAILED — partial results recovered

```python
    def test_t4_failed_run_partial_results(self, data_dir, sample_profiles, fake_apify):
        """T4: Apify FAILED, dataset has 3 of 5 results.
        
        Assert: results saved, 3 enriched, 2 failed (missing from results).
        State records run_status: FAILED.
        """
```

Implementation:
- Configure `fake_apify._terminal_status = "FAILED"` and `fake_apify._missing_urls = {url3, url4}`.
- Run pipeline.
- Assert: `results/{run_id}.json` saved. 3 profiles enriched. 2 logged as failed. State has `run_status: "FAILED"` in `batch_fetched` event.

#### T5: Apify run TIMED-OUT — partial results recovered

```python
    def test_t5_timedout_run_partial_results(self, data_dir, sample_profiles, fake_apify):
        """T5: Same as T4 but TIMED-OUT status. Verify same behavior."""
```

Same as T4 but `_terminal_status = "TIMED-OUT"`.

#### T6: Apify run ABORTED — possibly zero results

```python
    def test_t6_aborted_run_zero_results(self, data_dir, sample_profiles, fake_apify):
        """T6: ABORTED with 0 results. All 5 failed, no crash, state consistent."""
```

Configure: `_terminal_status = "ABORTED"`, `_missing_urls = all 5 URLs`.
Assert: 0 enriched, 5 failed, state file has `batch_completed`, no exception raised.

#### T7: Multi-batch crash — first batch done, crash during second

```python
    def test_t7_multi_batch_crash_resume_skips_done_batch(self, data_dir, fake_apify):
        """T7: 10 URLs, batch_size=5, 2 batches.
        
        Batch 0 completes. Crash during batch 1 polling.
        Resume: batch 0 skipped, batch 1 resumed.
        Assert: All 10 enriched. Batch 0 not re-processed.
        """
```

10 profiles, `max_batch_size=5`. First batch completes fully. Crash during second batch poll. Resume completes second batch. Assert batch 0 profiles not re-processed.

---

### Never-Lose-Paid-Data Tests (R1) — T8 through T10

#### T8: Results saved to disk before DB processing

```python
class TestNeverLoseData:
    def test_t8_results_on_disk_even_if_db_fails(self, data_dir, sample_profiles, fake_apify):
        """T8: DB write fails for all profiles.
        
        results/{run_id}.json exists with all 3 results.
        DB has 0 enriched. Data not lost.
        """
```

3 profiles. Mock DB writes to raise. Assert: results file exists with 3 items. DB enriched = 0.

#### T9: Partial results from failed run saved to disk

```python
    def test_t9_partial_results_saved(self, data_dir, sample_profiles, fake_apify):
        """T9: FAILED run, 2 of 5 results. File has exactly 2 items."""
```

#### T10: Results file is valid JSON with all Apify fields

```python
    def test_t10_results_file_valid_json(self, data_dir, sample_profiles, fake_apify):
        """T10: Results file round-trips through json.load().
        Contains linkedinUrl, firstName, experience, etc.
        """
```

---

### Idempotency Tests (R3) — T11 through T13

#### T11: Full pipeline run twice — same result

```python
class TestIdempotency:
    def test_t11_double_run_no_duplicates(self, data_dir, sample_profiles, fake_apify):
        """T11: Run pipeline twice for same profiles.
        
        Second run: 0 profiles enriched (query filter skips them).
        DB state identical after both runs.
        """
```

First run enriches 5. Mark profiles as `has_enriched_data=true`. Second run with same profiles (but now filtered out by query) → 0 enriched.

#### T12: Resume processes each profile exactly once

```python
    def test_t12_resume_no_double_processing(self, data_dir, sample_profiles, fake_apify):
        """T12: T3 scenario — verify process_enrichment_result called exactly 5 times total."""
```

Track mock call counts. 3 before crash + 2 on resume = 5 total. Never re-called for first 3.

#### T13: State file prevents re-submission of batches

```python
    def test_t13_completed_batches_not_resubmitted(self, data_dir, fake_apify):
        """T13: 2 batches both complete. Re-run: start_run never called."""
```

---

### Batch Embedding Tests — T14 through T16

#### T14: Batch embedding called once per Apify batch

```python
class TestBatchEmbedding:
    def test_t14_single_embed_call_per_batch(self, data_dir, sample_profiles, fake_apify):
        """T14: 5 profiles, 1 batch.
        
        embed(texts) called once with 5 texts.
        embed_single never called.
        """
```

Use `FakeEmbeddingProvider`. Assert `embed_call_count == 1`, `embed_single_call_count == 0`.

#### T15: --skip-embeddings defers embedding

```python
    def test_t15_skip_embeddings(self, data_dir, sample_profiles, fake_apify):
        """T15: skip_embeddings=True. embed() never called. Profiles have no vectors."""
```

#### T16: Embedding failure doesn't lose DB writes

```python
    def test_t16_embedding_failure_preserves_db(self, data_dir, sample_profiles, fake_apify):
        """T16: DB writes succeed. Embedding raises exception.
        
        All 3 profiles have has_enriched_data=true.
        Embeddings are null. Failed embeddings logged.
        """
```

`FakeEmbeddingProvider._should_fail = True`. Assert DB data preserved. Embedding columns null.

---

### Key Rotation / API Error Tests — T17 through T19

#### T17: 402 on batch start — rotate key, retry

```python
class TestKeyRotation:
    def test_t17_402_rotates_key(self, data_dir, sample_profiles):
        """T17: 2 keys. First returns 402. Second succeeds.
        
        Batch completes. First key marked exhausted.
        """
```

Create `KeyHealthTracker` with 2 keys. First call to `enrich_profiles_async` raises `ApifyCreditExhaustedError`. Pipeline should mark key exhausted, get next key, retry, succeed.

#### T18: All keys exhausted — stop gracefully

```python
    def test_t18_all_keys_exhausted_graceful_stop(self, data_dir):
        """T18: 2 batches, 1 key. Batch 1 succeeds. Key returns 402 on batch 2.
        
        Batch 1 fully processed. Batch 2 not started.
        stopped_reason = "all_keys_exhausted".
        """
```

#### T19: 429 — exponential backoff and retry

```python
    def test_t19_429_backoff_retry(self, data_dir, sample_profiles):
        """T19: First start_run returns 429. Second attempt succeeds.
        
        Batch completes. time.sleep called with backoff delay.
        """
```

Mock `time.sleep` to verify backoff was applied.

---

### Edge Cases — T20 through T28

#### T20: Empty input list — no-op

```python
class TestEdgeCases:
    def test_t20_empty_input_noop(self, data_dir):
        """T20: No profiles. No Apify calls, no state file, clean exit."""
```

#### T21: Single profile (batch_size=1 effectively)

```python
    def test_t21_single_profile(self, data_dir, fake_apify):
        """T21: 1 profile. Works same as batch. 1 Apify run with 1 URL."""
```

#### T22: All profiles missing from Apify results (empty dataset)

```python
    def test_t22_empty_dataset_all_failed(self, data_dir, sample_profiles, fake_apify):
        """T22: SUCCEEDED but empty dataset. All profiles failed. No crash."""
```

`fake_apify._missing_urls = all URLs`. Status SUCCEEDED. Assert 0 enriched, 5 failed.

#### T23: Result URL doesn't match any input URL

```python
    def test_t23_unexpected_result_ignored(self, data_dir, fake_apify):
        """T23: Extra result not in input. Ignored. Input profiles without match = failed."""
```

#### T24: Duplicate linkedinUrl in Apify results

```python
    def test_t24_duplicate_url_first_wins(self, data_dir, fake_apify):
        """T24: Two results with same linkedinUrl. First used, duplicate ignored."""
```

#### T25: Concurrent run rejected by lock file

```python
    def test_t25_lock_rejects_concurrent(self, data_dir):
        """T25: Lock file with current PID. Second run exits with error."""
```

Create lock file with `os.getpid()`. Attempt pipeline → `SystemExit` with "enrichment already running".

#### T26: Stale lock file reclaimed

```python
    def test_t26_stale_lock_dead_pid(self, data_dir, fake_apify, sample_profiles):
        """T26: Lock file with dead PID (999999). Pipeline reclaims, runs normally."""
```

#### T27: Lock file older than 6 hours reclaimed

```python
    def test_t27_stale_lock_old_timestamp(self, data_dir, fake_apify, sample_profiles):
        """T27: Lock with current PID but 7-hour-old timestamp. Reclaimed."""
```

Mock or set timestamp to 7 hours ago. Pipeline reclaims lock.

#### T28: fetch_results() timeout during dataset download

```python
    def test_t28_fetch_timeout_resume_retries(self, data_dir, sample_profiles, fake_apify):
        """T28: SUCCEEDED but fetch_results raises requests.Timeout.
        
        State has batch_started (not batch_fetched).
        Resume re-polls (SUCCEEDED again), retries fetch.
        """
```

First run: `fake_apify._error_on_fetch = requests.Timeout()`. State only has `batch_started`. Second run: clear error, resume from poll, fetch succeeds.

---

## Test Organization

```
tests/unit/enrichment_pipeline/test_bulk_enrichment.py
├── FakeApify (class)
├── FakeEmbeddingProvider (class, if not importable from existing test utils)
├── Fixtures (data_dir, state_path, results_dir, fake_apify, sample_profiles)
├── Helpers (read_state_events, count_events)
├── class TestRecovery
│   ├── test_t1_crash_during_polling_resume_completes
│   ├── test_t2_crash_after_fetch_resume_from_disk
│   ├── test_t3_crash_mid_processing_resume_skips_done
│   ├── test_t4_failed_run_partial_results
│   ├── test_t5_timedout_run_partial_results
│   ├── test_t6_aborted_run_zero_results
│   └── test_t7_multi_batch_crash_resume_skips_done_batch
├── class TestNeverLoseData
│   ├── test_t8_results_on_disk_even_if_db_fails
│   ├── test_t9_partial_results_saved
│   └── test_t10_results_file_valid_json
├── class TestIdempotency
│   ├── test_t11_double_run_no_duplicates
│   ├── test_t12_resume_no_double_processing
│   └── test_t13_completed_batches_not_resubmitted
├── class TestBatchEmbedding
│   ├── test_t14_single_embed_call_per_batch
│   ├── test_t15_skip_embeddings
│   └── test_t16_embedding_failure_preserves_db
├── class TestKeyRotation
│   ├── test_t17_402_rotates_key
│   ├── test_t18_all_keys_exhausted_graceful_stop
│   └── test_t19_429_backoff_retry
└── class TestEdgeCases
    ├── test_t20_empty_input_noop
    ├── test_t21_single_profile
    ├── test_t22_empty_dataset_all_failed
    ├── test_t23_unexpected_result_ignored
    ├── test_t24_duplicate_url_first_wins
    ├── test_t25_lock_rejects_concurrent
    ├── test_t26_stale_lock_dead_pid
    ├── test_t27_stale_lock_old_timestamp
    └── test_t28_fetch_timeout_resume_retries
```

---

## Verification Checklist

After completing SP4:

1. All 28 tests pass: `pytest backend/tests/unit/enrichment_pipeline/test_bulk_enrichment.py -v`
2. No flaky tests (all deterministic, no real I/O, no real time.sleep)
3. All existing tests still pass: `pytest backend/tests/unit/ -v`
4. Tests use `tmp_path` for all file I/O (no side effects)
5. FakeApify covers all configured behaviors needed by T1-T28
6. State file assertions verify exact event sequences (not just counts)
7. Each test is independent (no shared state between tests)
