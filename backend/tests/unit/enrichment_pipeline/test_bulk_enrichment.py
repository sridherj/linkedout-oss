# SPDX-License-Identifier: Apache-2.0
"""Unit tests for bulk_enrichment state, chunking, matching, and lock logic,
plus T1–T28 pipeline integration tests."""
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from linkedout.enrichment_pipeline.apify_client import (
    ApifyCreditExhaustedError,
    ApifyRateLimitError,
    AllKeysExhaustedError,
    KeyHealthTracker,
)
from linkedout.enrichment_pipeline.bulk_enrichment import (
    _append_state,
    _chunk_profiles,
    _load_state,
    _match_results,
    _save_results,
    _load_results,
    _acquire_lock,
    enrich_profiles,
    EnrichmentResult,
)


# ---------------------------------------------------------------------------
# _load_state / _append_state
# ---------------------------------------------------------------------------

class TestStateFile:

    def test_empty_file(self, tmp_path):
        state_path = tmp_path / 'state.jsonl'
        state_path.touch()
        assert _load_state(state_path) == {}

    def test_nonexistent_file(self, tmp_path):
        state_path = tmp_path / 'does-not-exist.jsonl'
        assert _load_state(state_path) == {}

    def test_full_lifecycle(self, tmp_path):
        state_path = tmp_path / 'state.jsonl'

        _append_state(state_path, {
            'type': 'batch_started', 'batch_idx': 0,
            'run_id': 'run1', 'urls': ['url1', 'url2'],
            'started_at': '2026-04-13T10:00:00+00:00',
        })
        _append_state(state_path, {
            'type': 'batch_fetched', 'batch_idx': 0,
            'run_id': 'run1', 'dataset_id': 'ds1',
            'run_status': 'SUCCEEDED', 'result_count': 2,
        })
        _append_state(state_path, {
            'type': 'profile_processed', 'batch_idx': 0,
            'linkedin_url': 'url1', 'profile_id': 'p1', 'status': 'enriched',
        })
        _append_state(state_path, {
            'type': 'profile_processed', 'batch_idx': 0,
            'linkedin_url': 'url2', 'profile_id': 'p2', 'status': 'failed',
        })
        _append_state(state_path, {
            'type': 'batch_completed', 'batch_idx': 0,
            'enriched': 1, 'failed': 1,
        })

        states = _load_state(state_path)
        assert 0 in states
        batch = states[0]
        assert batch.run_id == 'run1'
        assert batch.dataset_id == 'ds1'
        assert batch.run_status == 'SUCCEEDED'
        assert batch.result_count == 2
        assert batch.processed_urls == {'url1', 'url2'}
        assert batch.completed is True
        assert batch.urls == ['url1', 'url2']

    def test_multiple_batches(self, tmp_path):
        state_path = tmp_path / 'state.jsonl'
        _append_state(state_path, {
            'type': 'batch_started', 'batch_idx': 0,
            'run_id': 'r0', 'urls': ['a'],
        })
        _append_state(state_path, {
            'type': 'batch_started', 'batch_idx': 1,
            'run_id': 'r1', 'urls': ['b'],
        })
        states = _load_state(state_path)
        assert len(states) == 2
        assert states[0].run_id == 'r0'
        assert states[1].run_id == 'r1'

    def test_corrupt_line_skipped(self, tmp_path):
        state_path = tmp_path / 'state.jsonl'
        with open(state_path, 'w') as f:
            f.write('not valid json\n')
            f.write(json.dumps({
                'type': 'batch_started', 'batch_idx': 0,
                'run_id': 'r0', 'urls': ['a'],
            }) + '\n')
        states = _load_state(state_path)
        assert 0 in states
        assert states[0].run_id == 'r0'

    def test_append_creates_parent_dirs(self, tmp_path):
        state_path = tmp_path / 'nested' / 'dir' / 'state.jsonl'
        _append_state(state_path, {'type': 'test', 'batch_idx': 0})
        assert state_path.exists()

    def test_partial_state_started_only(self, tmp_path):
        """batch_started but no fetch → run_id present, dataset_id None."""
        state_path = tmp_path / 'state.jsonl'
        _append_state(state_path, {
            'type': 'batch_started', 'batch_idx': 0,
            'run_id': 'run1', 'urls': ['url1'],
        })
        states = _load_state(state_path)
        b = states[0]
        assert b.run_id == 'run1'
        assert b.dataset_id is None
        assert b.completed is False


# ---------------------------------------------------------------------------
# _chunk_profiles
# ---------------------------------------------------------------------------

class TestChunkProfiles:

    def test_exact_division(self):
        profiles = [('p1', 'u1'), ('p2', 'u2'), ('p3', 'u3'), ('p4', 'u4')]
        chunks = _chunk_profiles(profiles, 2)
        assert len(chunks) == 2
        assert chunks[0] == [('p1', 'u1'), ('p2', 'u2')]
        assert chunks[1] == [('p3', 'u3'), ('p4', 'u4')]

    def test_remainder(self):
        profiles = [('p1', 'u1'), ('p2', 'u2'), ('p3', 'u3')]
        chunks = _chunk_profiles(profiles, 2)
        assert len(chunks) == 2
        assert chunks[1] == [('p3', 'u3')]

    def test_single_batch(self):
        profiles = [('p1', 'u1'), ('p2', 'u2')]
        chunks = _chunk_profiles(profiles, 100)
        assert len(chunks) == 1
        assert chunks[0] == profiles

    def test_empty(self):
        assert _chunk_profiles([], 10) == []

    def test_batch_size_one(self):
        profiles = [('p1', 'u1'), ('p2', 'u2')]
        chunks = _chunk_profiles(profiles, 1)
        assert len(chunks) == 2


# ---------------------------------------------------------------------------
# _match_results
# ---------------------------------------------------------------------------

class TestMatchResults:

    def test_exact_match(self):
        urls = ['https://linkedin.com/in/alice', 'https://linkedin.com/in/bob']
        results = [
            {'linkedinUrl': 'https://linkedin.com/in/alice', 'name': 'Alice'},
            {'linkedinUrl': 'https://linkedin.com/in/bob', 'name': 'Bob'},
        ]
        matched, missing = _match_results(urls, results)
        assert len(matched) == 2
        assert missing == []

    def test_case_insensitive(self):
        urls = ['https://LinkedIn.com/in/Alice']
        results = [{'linkedinUrl': 'https://linkedin.com/in/alice', 'name': 'Alice'}]
        matched, missing = _match_results(urls, results)
        assert len(matched) == 1
        assert missing == []

    def test_trailing_slash_normalization(self):
        urls = ['https://linkedin.com/in/alice/']
        results = [{'linkedinUrl': 'https://linkedin.com/in/alice', 'name': 'Alice'}]
        matched, missing = _match_results(urls, results)
        assert len(matched) == 1

    def test_missing_urls(self):
        urls = ['https://linkedin.com/in/alice', 'https://linkedin.com/in/bob']
        results = [{'linkedinUrl': 'https://linkedin.com/in/alice', 'name': 'Alice'}]
        matched, missing = _match_results(urls, results)
        assert len(matched) == 1
        assert missing == ['https://linkedin.com/in/bob']

    def test_duplicate_results_first_wins(self):
        urls = ['https://linkedin.com/in/alice']
        results = [
            {'linkedinUrl': 'https://linkedin.com/in/alice', 'name': 'Alice1'},
            {'linkedinUrl': 'https://linkedin.com/in/alice', 'name': 'Alice2'},
        ]
        matched, missing = _match_results(urls, results)
        assert matched['https://linkedin.com/in/alice']['name'] == 'Alice1'

    def test_extra_results_ignored(self):
        urls = ['https://linkedin.com/in/alice']
        results = [
            {'linkedinUrl': 'https://linkedin.com/in/alice', 'name': 'Alice'},
            {'linkedinUrl': 'https://linkedin.com/in/charlie', 'name': 'Charlie'},
        ]
        matched, missing = _match_results(urls, results)
        assert len(matched) == 1
        assert missing == []

    def test_empty_inputs(self):
        matched, missing = _match_results([], [])
        assert matched == {}
        assert missing == []

    def test_result_missing_linkedinUrl_field(self):
        urls = ['https://linkedin.com/in/alice']
        results = [{'name': 'Alice'}]  # no linkedinUrl
        matched, missing = _match_results(urls, results)
        assert len(matched) == 0
        assert missing == ['https://linkedin.com/in/alice']

    def test_percent_encoded_url_matches_decoded(self):
        """DB stores %e3%83%87, Apify returns decoded ディル — must still match."""
        encoded_url = 'https://www.linkedin.com/in/dhirendra-singh-%e3%83%87%e3%82%a3%e3%83%ab-578b761ba'
        decoded_url = 'https://www.linkedin.com/in/dhirendra-singh-ディル-578b761ba'
        results = [{'linkedinUrl': decoded_url, 'firstName': 'Dhirendra'}]
        matched, missing = _match_results([encoded_url], results)
        assert len(matched) == 1
        assert encoded_url in matched
        assert missing == []


# ---------------------------------------------------------------------------
# _save_results / _load_results
# ---------------------------------------------------------------------------

class TestResultPersistence:

    def test_save_and_load(self, tmp_path):
        results_dir = tmp_path / 'results'
        data = [{'linkedinUrl': 'url1', 'name': 'Alice'}]
        path = _save_results(results_dir, 'run123', data)
        assert path.exists()
        loaded = _load_results(results_dir, 'run123')
        assert loaded == data

    def test_load_nonexistent(self, tmp_path):
        assert _load_results(tmp_path, 'nope') is None

    def test_creates_directory(self, tmp_path):
        results_dir = tmp_path / 'nested' / 'results'
        _save_results(results_dir, 'run1', [])
        assert results_dir.exists()


# ---------------------------------------------------------------------------
# _acquire_lock
# ---------------------------------------------------------------------------

class TestLockFile:

    def test_acquire_and_release(self, tmp_path):
        with _acquire_lock(tmp_path) as lock_path:
            assert lock_path.exists()
            lock_data = json.loads(lock_path.read_text())
            assert lock_data['pid'] == os.getpid()
        # Lock should be removed after context exit
        assert not lock_path.exists()

    def test_stale_lock_dead_pid(self, tmp_path):
        lock_dir = tmp_path / 'enrichment'
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / 'enrich.lock'
        lock_path.write_text(json.dumps({
            'pid': 999999999,  # almost certainly not a real PID
            'started_at': datetime.now(timezone.utc).isoformat(),
        }))

        # Should reclaim the stale lock
        with _acquire_lock(tmp_path) as acquired:
            assert acquired.exists()

    def test_stale_lock_old_timestamp(self, tmp_path):
        lock_dir = tmp_path / 'enrichment'
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / 'enrich.lock'
        old_time = datetime.now(timezone.utc) - timedelta(hours=7)
        lock_path.write_text(json.dumps({
            'pid': os.getpid(),  # our own PID — would block if not stale
            'started_at': old_time.isoformat(),
        }))

        # Should reclaim because timestamp is > 6 hours old
        with _acquire_lock(tmp_path) as acquired:
            assert acquired.exists()

    def test_active_lock_raises(self, tmp_path):
        lock_dir = tmp_path / 'enrichment'
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / 'enrich.lock'
        lock_path.write_text(json.dumps({
            'pid': os.getpid(),  # our own PID — alive
            'started_at': datetime.now(timezone.utc).isoformat(),
        }))

        with pytest.raises(SystemExit, match='already running'):
            with _acquire_lock(tmp_path):
                pass  # pragma: no cover

    def test_corrupt_lock_reclaimed(self, tmp_path):
        lock_dir = tmp_path / 'enrichment'
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / 'enrich.lock'
        lock_path.write_text('not json at all')

        with _acquire_lock(tmp_path) as acquired:
            assert acquired.exists()


# ===========================================================================
# T1–T28  Pipeline integration tests
# ===========================================================================

# ---------------------------------------------------------------------------
# Helpers / Fakes
# ---------------------------------------------------------------------------

def _make_profile_result(linkedin_url: str) -> dict:
    """Generate a realistic Apify result for a URL."""
    slug = linkedin_url.rstrip('/').split('/')[-1]
    return {
        'linkedinUrl': linkedin_url,
        'publicIdentifier': slug,
        'firstName': f'First_{slug}',
        'lastName': f'Last_{slug}',
        'headline': 'Engineer at TestCo',
        'about': f'About {slug}',
        'location': {
            'linkedinText': 'San Francisco, CA',
            'parsed': {'city': 'San Francisco', 'state': 'CA', 'country': 'US'},
        },
        'experience': [{
            'position': 'Software Engineer',
            'companyName': 'TestCo',
            'companyLinkedinUrl': 'https://linkedin.com/company/testco',
            'startDate': {'year': 2023, 'month': 1},
            'endDate': {'text': 'Present'},
        }],
        'education': [{
            'schoolName': 'Test University',
            'degree': 'BS',
            'fieldOfStudy': 'CS',
            'startDate': {'year': 2019},
            'endDate': {'year': 2023},
        }],
        'skills': [{'name': 'Python'}, {'name': 'Testing'}],
        'topSkills': ['Architecture'],
        'connectionsCount': 500,
    }


class FakeApifyClient:
    """Replaces LinkedOutApifyClient for pipeline tests.

    Instance-level state is shared via a class-level ``_shared`` dict so that
    every client created by the pipeline (which does ``LinkedOutApifyClient(key)``)
    operates on the same data.
    """

    _shared: dict | None = None  # set by the test before patching

    def __init__(self, api_key: str = 'fake-key'):
        self.api_key = api_key
        s = type(self)._shared
        if s is None:
            raise RuntimeError('FakeApifyClient._shared not initialised')
        self._s = s

    # -- dispatch --
    def enrich_profiles_async(self, urls: list[str]) -> str:
        self._s['start_call_count'] += 1
        err = self._s.get('error_on_start')
        if err is not None:
            # Pop once so retry succeeds (unless test re-sets it)
            if self._s.get('error_on_start_once'):
                self._s['error_on_start'] = None
                self._s['error_on_start_once'] = False
            raise err
        counter = self._s['run_counter'] = self._s.get('run_counter', 0) + 1
        run_id = f'fake_run_{counter}'
        dataset_id = f'fake_dataset_{counter}'
        missing = self._s.get('missing_urls', set())
        results = [_make_profile_result(u) for u in urls if u not in missing]
        self._s['runs'][run_id] = {
            'urls': urls, 'dataset_id': dataset_id,
            'status': self._s.get('terminal_status', 'SUCCEEDED'),
            'results': results,
        }
        return run_id

    # -- poll --
    def poll_run_safe(self, run_id: str, **kw) -> tuple[str, str]:
        self._s['poll_call_count'] += 1
        err = self._s.get('error_on_poll')
        if err is not None:
            if self._s.get('error_on_poll_once'):
                self._s['error_on_poll'] = None
                self._s['error_on_poll_once'] = False
            raise err
        run = self._s['runs'][run_id]
        return (run['status'], run['dataset_id'])

    # -- fetch --
    def fetch_results(self, dataset_id: str) -> list[dict]:
        self._s['fetch_call_count'] += 1
        err = self._s.get('error_on_fetch')
        if err is not None:
            if self._s.get('error_on_fetch_once'):
                self._s['error_on_fetch'] = None
                self._s['error_on_fetch_once'] = False
            raise err
        for run in self._s['runs'].values():
            if run['dataset_id'] == dataset_id:
                return run['results']
        return []


def _fresh_shared() -> dict:
    return {
        'runs': {},
        'run_counter': 0,
        'start_call_count': 0,
        'poll_call_count': 0,
        'fetch_call_count': 0,
    }


def _read_state_events(state_path: Path) -> list[dict]:
    if not state_path.exists():
        return []
    events = []
    for line in state_path.read_text().splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def _count_events(events: list[dict], event_type: str) -> int:
    return sum(1 for e in events if e.get('type') == event_type)


class _FakeConfig:
    """Minimal stand-in for get_config() used by enrich_profiles."""
    def __init__(self, data_dir: str = '/tmp/test-data'):
        self.data_dir = data_dir
        self.enrichment = _FakeEnrichmentCfg()


class _FakeEnrichmentCfg:
    apify_base_url = 'https://api.apify.com/v2'
    max_batch_size = 100
    run_poll_timeout_seconds = 10
    run_poll_interval_seconds = 0
    async_start_timeout_seconds = 5
    fetch_results_timeout_seconds = 5
    sync_timeout_seconds = 5
    key_validation_timeout_seconds = 5


# Patch targets (bulk_enrichment module's own imports)
_MOD = 'linkedout.enrichment_pipeline.bulk_enrichment'
_CLIENT_MOD = 'linkedout.enrichment_pipeline.apify_client'


@contextmanager
def _pipeline_patches(shared: dict, data_dir: str, batch_size: int = 100):
    """Context manager that patches LinkedOutApifyClient, get_config,
    get_platform_apify_key, and _validate_linkedin_url so enrich_profiles()
    runs against FakeApifyClient."""
    cfg = _FakeConfig(data_dir)
    cfg.enrichment.max_batch_size = batch_size
    FakeApifyClient._shared = shared
    with (
        patch(f'{_MOD}.LinkedOutApifyClient', FakeApifyClient),
        patch(f'{_MOD}.get_config', return_value=cfg),
        patch(f'{_MOD}.get_platform_apify_key', return_value='fake-platform-key'),
        patch(f'{_CLIENT_MOD}._validate_linkedin_url'),
    ):
        yield
    FakeApifyClient._shared = None


def _sample_profiles(n: int = 5) -> list[tuple[str, str]]:
    return [(f'cp_{i}', f'https://linkedin.com/in/person-{i}') for i in range(n)]


# ---------------------------------------------------------------------------
# Recovery Tests — T1 through T7
# ---------------------------------------------------------------------------

class TestRecovery:

    def test_t1_crash_during_polling_resume_completes(self, tmp_path):
        """T1: Crash after Apify run started, before poll completes.
        Resume re-polls same run_id, fetches, processes all 5."""
        profiles = _sample_profiles(5)
        shared = _fresh_shared()

        # --- Run 1: dispatch succeeds, poll raises to simulate crash ---
        shared['error_on_poll'] = RuntimeError('simulated crash')
        shared['error_on_poll_once'] = True

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)
        # Batch not completed (poll failed)
        assert result.batches_completed == 0
        assert shared['start_call_count'] == 1

        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        events = _read_state_events(state_path)
        assert _count_events(events, 'batch_started') == 1

        # --- Run 2: resume — poll succeeds now ---
        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)
        assert result.enriched == 5
        assert result.batches_completed == 1
        # enrich_profiles_async should NOT have been called again
        assert shared['start_call_count'] == 1

    def test_t2_crash_after_fetch_resume_from_disk(self, tmp_path):
        """T2: Results saved to disk, crash before DB writes.
        Resume re-reads from disk, processes all 5."""
        profiles = _sample_profiles(5)
        shared = _fresh_shared()

        # --- Run 1: dispatch+poll+fetch succeeds, processing crashes.
        # The exception propagates out of enrich_profiles (not caught).
        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            with patch(f'{_MOD}._process_batch_results', side_effect=Exception('crash')):
                with pytest.raises(Exception, match='crash'):
                    enrich_profiles(profiles, data_dir=tmp_path)
        assert shared['fetch_call_count'] == 1

        # State has batch_started + batch_fetched. Results file on disk.
        results_dir = tmp_path / 'enrichment' / 'results'
        result_files = list(results_dir.glob('*.json'))
        assert len(result_files) == 1

        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        events = _read_state_events(state_path)
        assert _count_events(events, 'batch_fetched') == 1

        # --- Run 2: resume from disk (no patch — real processing) ---
        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)
        assert result.enriched == 5
        assert result.batches_completed == 1
        # fetch_results should NOT have been called again
        assert shared['fetch_call_count'] == 1

    def test_t3_crash_mid_processing_resume_skips_done(self, tmp_path):
        """T3: 3 of 5 profiles processed, crash on 4th.
        Resume skips done profiles, processes remaining 2."""
        profiles = _sample_profiles(5)
        shared = _fresh_shared()

        # --- Run 1: dispatch+poll+fetch succeed, processing crashes.
        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            with patch(f'{_MOD}._process_batch_results', side_effect=Exception('crash')):
                with pytest.raises(Exception, match='crash'):
                    enrich_profiles(profiles, data_dir=tmp_path)

        # Manually write partial state: 3 profiles processed (simulating
        # what would happen if processing crashed after 3 of 5)
        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        for i in range(3):
            _append_state(state_path, {
                'type': 'profile_processed',
                'batch_idx': 0,
                'linkedin_url': f'https://linkedin.com/in/person-{i}',
                'profile_id': f'cp_{i}',
                'status': 'enriched',
            })

        # --- Run 2: resume (no patch — real processing) ---
        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.batches_completed == 1
        # 3 already done + 2 newly processed = 5 total enriched
        assert result.enriched == 5

    def test_t4_failed_run_partial_results(self, tmp_path):
        """T4: Apify FAILED, dataset has 3 of 5 results.
        3 enriched, 2 failed (missing from results)."""
        profiles = _sample_profiles(5)
        shared = _fresh_shared()
        shared['terminal_status'] = 'FAILED'
        shared['missing_urls'] = {
            'https://linkedin.com/in/person-3',
            'https://linkedin.com/in/person-4',
        }

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.enriched == 3
        assert result.failed == 2
        assert result.batches_completed == 1

        # Results file saved
        results_dir = tmp_path / 'enrichment' / 'results'
        result_files = list(results_dir.glob('*.json'))
        assert len(result_files) == 1
        saved = json.loads(result_files[0].read_text())
        assert len(saved) == 3

        # State records FAILED status
        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        events = _read_state_events(state_path)
        fetched = [e for e in events if e['type'] == 'batch_fetched']
        assert fetched[0]['run_status'] == 'FAILED'

    def test_t5_timedout_run_partial_results(self, tmp_path):
        """T5: Same as T4 but TIMED-OUT status."""
        profiles = _sample_profiles(5)
        shared = _fresh_shared()
        shared['terminal_status'] = 'TIMED-OUT'
        shared['missing_urls'] = {
            'https://linkedin.com/in/person-3',
            'https://linkedin.com/in/person-4',
        }

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.enriched == 3
        assert result.failed == 2

    def test_t6_aborted_run_zero_results(self, tmp_path):
        """T6: ABORTED with 0 results. All 5 failed, no crash."""
        profiles = _sample_profiles(5)
        shared = _fresh_shared()
        shared['terminal_status'] = 'ABORTED'
        shared['missing_urls'] = {f'https://linkedin.com/in/person-{i}' for i in range(5)}

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.enriched == 0
        assert result.failed == 5
        assert result.batches_completed == 1
        assert result.stopped_reason is None  # completed, just nothing enriched

    def test_t7_multi_batch_crash_resume_skips_done_batch(self, tmp_path):
        """T7: 10 URLs, batch_size=5. Batch 0 completes, crash during batch 1.
        Resume: batch 0 skipped, batch 1 resumed."""
        profiles = _sample_profiles(10)
        shared = _fresh_shared()

        # Allow first batch to succeed, crash on second batch's poll
        poll_count = {'n': 0}
        _orig_poll = FakeApifyClient.poll_run_safe

        def _crashing_poll(self_client, run_id, **kw):
            poll_count['n'] += 1
            if poll_count['n'] == 2:  # second batch poll
                raise RuntimeError('crash during batch 1 poll')
            return _orig_poll(self_client, run_id, **kw)

        with _pipeline_patches(shared, str(tmp_path), batch_size=5):
            with patch.object(FakeApifyClient, 'poll_run_safe', _crashing_poll):
                result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.batches_completed == 1  # only batch 0
        assert shared['start_call_count'] == 2  # both submitted

        # --- Resume: batch 0 skipped, batch 1 finishes ---
        with _pipeline_patches(shared, str(tmp_path), batch_size=5):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.batches_completed == 2
        assert result.enriched == 10
        # enrich_profiles_async NOT called again for either batch
        assert shared['start_call_count'] == 2


# ---------------------------------------------------------------------------
# Never-Lose-Data Tests — T8 through T10
# ---------------------------------------------------------------------------

class TestNeverLoseData:

    def test_t8_results_on_disk_even_if_db_fails(self, tmp_path):
        """T8: DB write fails for all profiles.
        results/{run_id}.json exists with all 3 results."""
        profiles = _sample_profiles(3)
        shared = _fresh_shared()

        def _failing_session_factory():
            raise Exception('DB connection failed')

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(
                profiles, data_dir=tmp_path,
                db_session_factory=_failing_session_factory,
                post_enrichment_factory=lambda s: MagicMock(),
            )

        # Results file saved to disk even though DB fails
        results_dir = tmp_path / 'enrichment' / 'results'
        result_files = list(results_dir.glob('*.json'))
        assert len(result_files) == 1
        saved = json.loads(result_files[0].read_text())
        assert len(saved) == 3

    def test_t9_partial_results_saved(self, tmp_path):
        """T9: FAILED run, 2 of 5 results. File has exactly 2 items."""
        profiles = _sample_profiles(5)
        shared = _fresh_shared()
        shared['terminal_status'] = 'FAILED'
        shared['missing_urls'] = {
            f'https://linkedin.com/in/person-{i}' for i in range(2, 5)
        }

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            enrich_profiles(profiles, data_dir=tmp_path)

        results_dir = tmp_path / 'enrichment' / 'results'
        result_files = list(results_dir.glob('*.json'))
        assert len(result_files) == 1
        saved = json.loads(result_files[0].read_text())
        assert len(saved) == 2

    def test_t10_results_file_valid_json(self, tmp_path):
        """T10: Results file round-trips through json.load().
        Contains linkedinUrl, firstName, experience, etc."""
        profiles = _sample_profiles(3)
        shared = _fresh_shared()

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            enrich_profiles(profiles, data_dir=tmp_path)

        results_dir = tmp_path / 'enrichment' / 'results'
        result_files = list(results_dir.glob('*.json'))
        saved = json.loads(result_files[0].read_text())
        assert isinstance(saved, list)
        assert len(saved) == 3
        for item in saved:
            assert 'linkedinUrl' in item
            assert 'firstName' in item
            assert 'experience' in item


# ---------------------------------------------------------------------------
# Idempotency Tests — T11 through T13
# ---------------------------------------------------------------------------

class TestIdempotency:

    def test_t11_double_run_no_duplicates(self, tmp_path):
        """T11: Run pipeline twice for same profiles.
        Second run: batch already completed → skipped."""
        profiles = _sample_profiles(5)
        shared = _fresh_shared()

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            r1 = enrich_profiles(profiles, data_dir=tmp_path)
        assert r1.enriched == 5
        assert r1.batches_completed == 1

        # Second run — batch already completed in state file
        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            r2 = enrich_profiles(profiles, data_dir=tmp_path)
        assert r2.batches_completed == 1  # recognised from state
        # enrich_profiles_async only called once total
        assert shared['start_call_count'] == 1

    def test_t12_resume_no_double_processing(self, tmp_path):
        """T12: T3 scenario — verify profiles not re-processed after resume."""
        profiles = _sample_profiles(5)
        shared = _fresh_shared()

        # Run 1: succeeds fully
        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            r1 = enrich_profiles(profiles, data_dir=tmp_path)
        assert r1.enriched == 5

        events = _read_state_events(tmp_path / 'enrichment' / 'enrich-state.jsonl')
        processed = [e for e in events if e['type'] == 'profile_processed']
        assert len(processed) == 5

        # Run 2: batch is completed → skip entirely
        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            r2 = enrich_profiles(profiles, data_dir=tmp_path)

        # No new profile_processed events should be written
        events2 = _read_state_events(tmp_path / 'enrichment' / 'enrich-state.jsonl')
        processed2 = [e for e in events2 if e['type'] == 'profile_processed']
        assert len(processed2) == 5  # same as before, no duplicates

    def test_t13_completed_batches_not_resubmitted(self, tmp_path):
        """T13: 2 batches both complete. Re-run: start_run never called again."""
        profiles = _sample_profiles(10)
        shared = _fresh_shared()

        with _pipeline_patches(shared, str(tmp_path), batch_size=5):
            r1 = enrich_profiles(profiles, data_dir=tmp_path)
        assert r1.batches_completed == 2
        assert shared['start_call_count'] == 2

        # Re-run: both batches completed in state → skip
        with _pipeline_patches(shared, str(tmp_path), batch_size=5):
            r2 = enrich_profiles(profiles, data_dir=tmp_path)
        assert r2.batches_completed == 2
        # No new calls to enrich_profiles_async
        assert shared['start_call_count'] == 2


# ---------------------------------------------------------------------------
# Batch Embedding Tests — T14 through T16
# ---------------------------------------------------------------------------

class TestBatchEmbedding:

    def test_t14_single_embed_call_per_batch(self, tmp_path):
        """T14: 5 profiles, 1 batch. process_batch called once.
        Verify DB factory and post_enrichment_factory invoked."""
        profiles = _sample_profiles(5)
        shared = _fresh_shared()

        mock_service = MagicMock()
        mock_service.process_batch.return_value = (5, 0)
        mock_session = MagicMock()

        @contextmanager
        def session_factory():
            yield mock_session

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(
                profiles, data_dir=tmp_path,
                db_session_factory=session_factory,
                post_enrichment_factory=lambda s: mock_service,
            )

        assert result.enriched == 5
        assert mock_service.process_batch.call_count == 1
        # process_batch receives list of (profile_id, url, apify_data) tuples
        call_args = mock_service.process_batch.call_args
        assert len(call_args[0][0]) == 5  # 5 profiles in the batch

    def test_t15_skip_embeddings(self, tmp_path):
        """T15: skip_embeddings=True passed through to process_batch."""
        profiles = _sample_profiles(3)
        shared = _fresh_shared()

        mock_service = MagicMock()
        mock_service.process_batch.return_value = (3, 0)

        @contextmanager
        def session_factory():
            yield MagicMock()

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            enrich_profiles(
                profiles, data_dir=tmp_path,
                db_session_factory=session_factory,
                post_enrichment_factory=lambda s: mock_service,
                skip_embeddings=True,
            )

        call_kwargs = mock_service.process_batch.call_args
        assert call_kwargs[1]['skip_embeddings'] is True

    def test_t16_embedding_failure_preserves_db(self, tmp_path):
        """T16: DB writes succeed but process_batch raises on embedding.
        _process_batch_results catches the exception, counts profiles as
        failed, but batch still completes. Results file on disk (R1)."""
        profiles = _sample_profiles(3)
        shared = _fresh_shared()

        mock_service = MagicMock()
        mock_service.process_batch.side_effect = Exception('embedding explosion')

        @contextmanager
        def session_factory():
            yield MagicMock()

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(
                profiles, data_dir=tmp_path,
                db_session_factory=session_factory,
                post_enrichment_factory=lambda s: mock_service,
            )

        # All 3 counted as failed since process_batch raised
        assert result.failed == 3
        # Batch still records as completed (the exception is caught)
        assert result.batches_completed == 1

        # Results file still on disk (R1 — persisted before DB work)
        results_dir = tmp_path / 'enrichment' / 'results'
        result_files = list(results_dir.glob('*.json'))
        assert len(result_files) == 1


# ---------------------------------------------------------------------------
# Key Rotation / API Error Tests — T17 through T19
# ---------------------------------------------------------------------------

class TestKeyRotation:

    def test_t17_402_rotates_key(self, tmp_path):
        """T17: 2 keys. First returns 402. Second succeeds."""
        profiles = _sample_profiles(3)
        shared = _fresh_shared()
        tracker = KeyHealthTracker(['key_a', 'key_b'])

        # First call raises 402, then pipeline rotates and retries
        shared['error_on_start'] = ApifyCreditExhaustedError('402', status_code=402)
        shared['error_on_start_once'] = True

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path, key_tracker=tracker)

        assert result.enriched == 3
        assert result.batches_completed == 1
        # start was called twice (first 402, then success)
        assert shared['start_call_count'] == 2

    def test_t18_all_keys_exhausted_graceful_stop(self, tmp_path):
        """T18: 2 batches, all keys return 402 on batch 2.
        Batch 1 fully processed. stopped_reason = 'all_keys_exhausted'."""
        profiles = _sample_profiles(10)
        tracker = KeyHealthTracker(['key_a'])

        shared = _fresh_shared()
        dispatch_count = {'n': 0}

        _orig_async = FakeApifyClient.enrich_profiles_async

        def _exhausting_async(self_client, urls):
            dispatch_count['n'] += 1
            if dispatch_count['n'] == 2:
                raise ApifyCreditExhaustedError('402', status_code=402)
            return _orig_async(self_client, urls)

        with _pipeline_patches(shared, str(tmp_path), batch_size=5):
            with patch.object(FakeApifyClient, 'enrich_profiles_async', _exhausting_async):
                result = enrich_profiles(profiles, data_dir=tmp_path, key_tracker=tracker)

        assert result.batches_completed == 1
        assert result.enriched == 5
        assert result.stopped_reason == 'all_keys_exhausted'

    def test_t19_429_backoff_retry(self, tmp_path):
        """T19: First start_run returns 429. Second attempt succeeds.
        time.sleep called with backoff delay."""
        profiles = _sample_profiles(3)
        shared = _fresh_shared()
        shared['error_on_start'] = ApifyRateLimitError('429', status_code=429)
        shared['error_on_start_once'] = True

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            with patch(f'{_MOD}.time.sleep') as mock_sleep:
                result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.enriched == 3
        assert result.batches_completed == 1
        # time.sleep called with backoff delay (base 2s * 2^0 = 2)
        mock_sleep.assert_called_once_with(2)


# ---------------------------------------------------------------------------
# Edge Cases — T20 through T28
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_t20_empty_input_noop(self, tmp_path):
        """T20: No profiles. No Apify calls, no state file, clean exit."""
        shared = _fresh_shared()

        with _pipeline_patches(shared, str(tmp_path)):
            result = enrich_profiles([], data_dir=tmp_path)

        assert result == EnrichmentResult(
            total_profiles=0, enriched=0, failed=0,
            batches_completed=0, batches_total=0,
        )
        assert shared['start_call_count'] == 0
        # No state file created
        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        assert not state_path.exists()

    def test_t21_single_profile(self, tmp_path):
        """T21: 1 profile. Works same as batch. 1 Apify run with 1 URL."""
        profiles = _sample_profiles(1)
        shared = _fresh_shared()

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.enriched == 1
        assert result.batches_completed == 1
        assert result.batches_total == 1
        assert shared['start_call_count'] == 1

    def test_t22_empty_dataset_all_failed(self, tmp_path):
        """T22: SUCCEEDED but empty dataset. All profiles failed. No crash."""
        profiles = _sample_profiles(5)
        shared = _fresh_shared()
        shared['missing_urls'] = {f'https://linkedin.com/in/person-{i}' for i in range(5)}

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.enriched == 0
        assert result.failed == 5
        assert result.batches_completed == 1

    def test_t23_unexpected_result_ignored(self, tmp_path):
        """T23: Extra result not in input. Ignored. Input profiles without match = failed."""
        profiles = [('cp_0', 'https://linkedin.com/in/person-0')]
        shared = _fresh_shared()
        shared['missing_urls'] = {'https://linkedin.com/in/person-0'}

        # Manually inject an extra URL result that the pipeline didn't ask for
        _orig_async = FakeApifyClient.enrich_profiles_async

        def _extra_result_async(self_client, urls):
            run_id = _orig_async(self_client, urls)
            # Add an unexpected result
            run = self_client._s['runs'][run_id]
            run['results'].append(_make_profile_result('https://linkedin.com/in/stranger'))
            return run_id

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            with patch.object(FakeApifyClient, 'enrich_profiles_async', _extra_result_async):
                result = enrich_profiles(profiles, data_dir=tmp_path)

        # person-0 still missing, stranger ignored
        assert result.failed == 1
        assert result.enriched == 0

    def test_t24_duplicate_url_first_wins(self, tmp_path):
        """T24: Two results with same linkedinUrl. First used, duplicate ignored."""
        profiles = [('cp_0', 'https://linkedin.com/in/person-0')]
        shared = _fresh_shared()

        _orig_async = FakeApifyClient.enrich_profiles_async

        def _dup_result_async(self_client, urls):
            run_id = _orig_async(self_client, urls)
            run = self_client._s['runs'][run_id]
            # Add duplicate with different name
            dup = _make_profile_result('https://linkedin.com/in/person-0')
            dup['firstName'] = 'Duplicate'
            run['results'].append(dup)
            return run_id

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            with patch.object(FakeApifyClient, 'enrich_profiles_async', _dup_result_async):
                result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.enriched == 1
        # Verify first result was used (not the duplicate) via saved file
        results_dir = tmp_path / 'enrichment' / 'results'
        result_files = list(results_dir.glob('*.json'))
        saved = json.loads(result_files[0].read_text())
        # Both are in the raw file (saved as-is from Apify)
        assert len(saved) == 2
        # But _match_results uses first occurrence — verified by existing TestMatchResults

    def test_t25_lock_rejects_concurrent(self, tmp_path):
        """T25: Lock file with current PID. Second run exits with error."""
        lock_dir = tmp_path / 'enrichment'
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / 'enrich.lock'
        lock_path.write_text(json.dumps({
            'pid': os.getpid(),
            'started_at': datetime.now(timezone.utc).isoformat(),
        }))

        profiles = _sample_profiles(3)
        shared = _fresh_shared()

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            with pytest.raises(SystemExit, match='already running'):
                enrich_profiles(profiles, data_dir=tmp_path)

        assert shared['start_call_count'] == 0

    def test_t26_stale_lock_dead_pid(self, tmp_path):
        """T26: Lock file with dead PID (999999). Pipeline reclaims, runs normally."""
        lock_dir = tmp_path / 'enrichment'
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / 'enrich.lock'
        lock_path.write_text(json.dumps({
            'pid': 999999999,
            'started_at': datetime.now(timezone.utc).isoformat(),
        }))

        profiles = _sample_profiles(3)
        shared = _fresh_shared()

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.enriched == 3

    def test_t27_stale_lock_old_timestamp(self, tmp_path):
        """T27: Lock with current PID but 7-hour-old timestamp. Reclaimed."""
        lock_dir = tmp_path / 'enrichment'
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / 'enrich.lock'
        old_time = datetime.now(timezone.utc) - timedelta(hours=7)
        lock_path.write_text(json.dumps({
            'pid': os.getpid(),
            'started_at': old_time.isoformat(),
        }))

        profiles = _sample_profiles(3)
        shared = _fresh_shared()

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.enriched == 3

    def test_t28_fetch_timeout_resume_retries(self, tmp_path):
        """T28: SUCCEEDED but fetch_results raises timeout.
        State has batch_started (not batch_fetched).
        Resume re-polls, retries fetch successfully."""
        import requests as req_lib

        profiles = _sample_profiles(3)
        shared = _fresh_shared()

        # First run: fetch raises timeout
        shared['error_on_fetch'] = req_lib.Timeout('fetch timed out')
        shared['error_on_fetch_once'] = True

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)
        # batch_started recorded but poll+fetch failed → no completion
        assert result.batches_completed == 0

        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        events = _read_state_events(state_path)
        assert _count_events(events, 'batch_started') == 1
        assert _count_events(events, 'batch_fetched') == 0

        # Resume: fetch succeeds now
        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.enriched == 3
        assert result.batches_completed == 1
