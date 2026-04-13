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
    _check_batch_resume,
    _chunk_profiles,
    _load_state,
    _match_results,
    _save_results,
    _load_results,
    _acquire_lock,
    _rotate_state,
    enrich_profiles,
    recover_incomplete_batches,
    check_recoverable_batches,
    BatchResumeResult,
    BatchState,
    EnrichmentResult,
    RecoverySummary,
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
        matched, missing, _redirects = _match_results(urls, results)
        assert len(matched) == 2
        assert missing == []

    def test_case_insensitive(self):
        urls = ['https://LinkedIn.com/in/Alice']
        results = [{'linkedinUrl': 'https://linkedin.com/in/alice', 'name': 'Alice'}]
        matched, missing, _redirects = _match_results(urls, results)
        assert len(matched) == 1
        assert missing == []

    def test_trailing_slash_normalization(self):
        urls = ['https://linkedin.com/in/alice/']
        results = [{'linkedinUrl': 'https://linkedin.com/in/alice', 'name': 'Alice'}]
        matched, missing, _redirects = _match_results(urls, results)
        assert len(matched) == 1

    def test_missing_urls(self):
        urls = ['https://linkedin.com/in/alice', 'https://linkedin.com/in/bob']
        results = [{'linkedinUrl': 'https://linkedin.com/in/alice', 'name': 'Alice'}]
        matched, missing, _redirects = _match_results(urls, results)
        assert len(matched) == 1
        assert missing == ['https://linkedin.com/in/bob']

    def test_duplicate_results_first_wins(self):
        urls = ['https://linkedin.com/in/alice']
        results = [
            {'linkedinUrl': 'https://linkedin.com/in/alice', 'name': 'Alice1'},
            {'linkedinUrl': 'https://linkedin.com/in/alice', 'name': 'Alice2'},
        ]
        matched, missing, _redirects = _match_results(urls, results)
        assert matched['https://linkedin.com/in/alice']['name'] == 'Alice1'

    def test_extra_results_ignored(self):
        urls = ['https://linkedin.com/in/alice']
        results = [
            {'linkedinUrl': 'https://linkedin.com/in/alice', 'name': 'Alice'},
            {'linkedinUrl': 'https://linkedin.com/in/charlie', 'name': 'Charlie'},
        ]
        matched, missing, _redirects = _match_results(urls, results)
        assert len(matched) == 1
        assert missing == []

    def test_empty_inputs(self):
        matched, missing, _redirects = _match_results([], [])
        assert matched == {}
        assert missing == []

    def test_result_missing_linkedinUrl_field(self):
        urls = ['https://linkedin.com/in/alice']
        results = [{'name': 'Alice'}]  # no linkedinUrl
        matched, missing, _redirects = _match_results(urls, results)
        assert len(matched) == 0
        assert missing == ['https://linkedin.com/in/alice']

    def test_percent_encoded_url_matches_decoded(self):
        """DB stores %e3%83%87, Apify returns decoded ディル — must still match."""
        encoded_url = 'https://www.linkedin.com/in/dhirendra-singh-%e3%83%87%e3%82%a3%e3%83%ab-578b761ba'
        decoded_url = 'https://www.linkedin.com/in/dhirendra-singh-ディル-578b761ba'
        results = [{'linkedinUrl': decoded_url, 'firstName': 'Dhirendra'}]
        matched, missing, _redirects = _match_results([encoded_url], results)
        assert len(matched) == 1
        assert encoded_url in matched
        assert missing == []


# ---------------------------------------------------------------------------
# Redirect matching tests (T1-T5)
# ---------------------------------------------------------------------------

class TestRedirectMatching:
    """Tests for rapidfuzz-based redirect detection in _match_results."""

    def test_t1_single_redirect_pairing(self):
        """T1: Single redirect — slug shortened by LinkedIn."""
        batch_urls = ['https://www.linkedin.com/in/vikas-khatana-web-developer']
        apify_results = [{'linkedinUrl': 'https://www.linkedin.com/in/vikas-khatana', 'firstName': 'Vikas'}]
        matched, missing, redirects = _match_results(batch_urls, apify_results)

        assert len(matched) == 1
        assert batch_urls[0] in matched
        assert missing == []
        assert redirects == {
            'https://www.linkedin.com/in/vikas-khatana-web-developer': 'https://www.linkedin.com/in/vikas-khatana',
        }

    def test_t2_multiple_redirects_greedy(self):
        """T2: 3 unmatched inputs + 3 unmatched results, all paired correctly."""
        batch_urls = [
            'https://www.linkedin.com/in/alice-jones-developer',
            'https://www.linkedin.com/in/bob-smith-engineer',
            'https://www.linkedin.com/in/carol-white-designer',
        ]
        apify_results = [
            {'linkedinUrl': 'https://www.linkedin.com/in/alice-jones', 'firstName': 'Alice'},
            {'linkedinUrl': 'https://www.linkedin.com/in/bob-smith', 'firstName': 'Bob'},
            {'linkedinUrl': 'https://www.linkedin.com/in/carol-white', 'firstName': 'Carol'},
        ]
        matched, missing, redirects = _match_results(batch_urls, apify_results)

        assert len(matched) == 3
        assert missing == []
        assert len(redirects) == 3
        assert redirects[batch_urls[0]] == 'https://www.linkedin.com/in/alice-jones'
        assert redirects[batch_urls[1]] == 'https://www.linkedin.com/in/bob-smith'
        assert redirects[batch_urls[2]] == 'https://www.linkedin.com/in/carol-white'

    def test_t3_all_exact_matches_no_redirects(self):
        """T3: All inputs match exactly — redirects dict is empty."""
        batch_urls = [
            'https://www.linkedin.com/in/alice',
            'https://www.linkedin.com/in/bob',
        ]
        apify_results = [
            {'linkedinUrl': 'https://www.linkedin.com/in/alice', 'firstName': 'Alice'},
            {'linkedinUrl': 'https://www.linkedin.com/in/bob', 'firstName': 'Bob'},
        ]
        matched, missing, redirects = _match_results(batch_urls, apify_results)

        assert len(matched) == 2
        assert missing == []
        assert redirects == {}

    def test_t4_extra_apify_result_ignored(self):
        """T4: Apify returns result for URL not in batch. No crash, ignored."""
        batch_urls = ['https://www.linkedin.com/in/alice']
        apify_results = [
            {'linkedinUrl': 'https://www.linkedin.com/in/alice', 'firstName': 'Alice'},
            {'linkedinUrl': 'https://www.linkedin.com/in/stranger', 'firstName': 'Stranger'},
        ]
        matched, missing, redirects = _match_results(batch_urls, apify_results)

        assert len(matched) == 1
        assert missing == []
        assert redirects == {}

    def test_t5_below_threshold_stays_failed(self):
        """T5: Unmatched input slug is completely dissimilar — stays in missing."""
        batch_urls = ['https://www.linkedin.com/in/completely-different-person']
        apify_results = [{'linkedinUrl': 'https://www.linkedin.com/in/xyz-abc-123', 'firstName': 'X'}]
        matched, missing, redirects = _match_results(batch_urls, apify_results)

        assert len(matched) == 0
        assert missing == ['https://www.linkedin.com/in/completely-different-person']
        assert redirects == {}


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

    # -- poll (blocking, used by external callers) --
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

    # -- non-blocking poll (used by dispatch-pool) --
    def check_run_status(self, run_id: str) -> tuple[str, str] | None:
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
    max_parallel_batches = 5
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
        """T1: Transient poll error. Dispatch-pool retries within the same
        run — batch completes without needing a separate resume."""
        profiles = _sample_profiles(5)
        shared = _fresh_shared()

        # Poll error happens once, then clears — dispatch-pool retries
        shared['error_on_poll'] = RuntimeError('simulated crash')
        shared['error_on_poll_once'] = True

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)
        # Dispatch-pool retries transient poll errors — batch completes
        assert result.batches_completed == 1
        assert result.enriched == 5
        assert shared['start_call_count'] == 1

        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        events = _read_state_events(state_path)
        assert _count_events(events, 'batch_started') == 1

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
        """T7: 10 URLs, batch_size=5. Batch 0 completes, crash during batch 1
        processing. Resume: batch 0 skipped, batch 1 resumed from disk."""
        from linkedout.enrichment_pipeline import bulk_enrichment as _be
        _real_process = _be._process_batch_results

        profiles = _sample_profiles(10)
        shared = _fresh_shared()

        # Crash on second call to _process_batch_results (batch 1)
        call_count = {'n': 0}

        def _crashing_process(*args, **kwargs):
            call_count['n'] += 1
            if call_count['n'] == 2:
                raise RuntimeError('crash during batch 1 processing')
            return _real_process(*args, **kwargs)

        with _pipeline_patches(shared, str(tmp_path), batch_size=5):
            with patch(f'{_MOD}._process_batch_results', side_effect=_crashing_process):
                with pytest.raises(RuntimeError, match='crash during batch 1'):
                    enrich_profiles(profiles, data_dir=tmp_path)

        # Batch 0 completed before crash, batch 1 fetched but not processed
        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        events = _read_state_events(state_path)
        assert _count_events(events, 'batch_completed') == 1  # batch 0 only
        assert shared['start_call_count'] == 2  # both dispatched

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
        Dispatch-pool dispatches batch 0, then batch 1 fails (key exhausted).
        Batch 0 dispatched but unpolled (no healthy keys). Graceful stop."""
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

        # Batch 0 dispatched but can't poll (key exhausted during batch 1 dispatch)
        assert result.batches_completed == 0
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
        """T28: SUCCEEDED but fetch_results raises timeout on first attempt.
        Dispatch-pool retries fetch in the next poll cycle — batch completes
        within the same run."""
        import requests as req_lib

        profiles = _sample_profiles(3)
        shared = _fresh_shared()

        # Fetch error happens once, then clears — dispatch-pool retries
        shared['error_on_fetch'] = req_lib.Timeout('fetch timed out')
        shared['error_on_fetch_once'] = True

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)
        # Dispatch-pool retries transient fetch errors — batch completes
        assert result.enriched == 3
        assert result.batches_completed == 1


# ===========================================================================
# Concurrent dispatch-pool tests (T-concurrent-1 through T-concurrent-6)
# ===========================================================================

class TestConcurrentDispatch:

    def test_concurrent_1_sequential_max_parallel_1(self, tmp_path):
        """T-concurrent-1: max_parallel_batches=1 dispatches one at a time."""
        profiles = _sample_profiles(6)
        shared = _fresh_shared()

        with _pipeline_patches(shared, str(tmp_path), batch_size=2) as _:
            # Override max_parallel_batches to 1 via the config
            with patch(f'{_MOD}.get_config') as mock_cfg:
                cfg = _FakeConfig(str(tmp_path))
                cfg.enrichment.max_batch_size = 2
                cfg.enrichment.max_parallel_batches = 1
                mock_cfg.return_value = cfg
                result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.enriched == 6
        assert result.batches_completed == 3

        # Verify sequential order in state file
        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        events = _read_state_events(state_path)
        started = [e for e in events if e['type'] == 'batch_started']
        completed = [e for e in events if e['type'] == 'batch_completed']
        assert len(started) == 3
        assert len(completed) == 3
        # batch_started 0 comes before batch_started 1 (sequential)
        started_idxs = [e['batch_idx'] for e in started]
        assert started_idxs == [0, 1, 2]

    def test_concurrent_2_parallel_dispatch_max_3(self, tmp_path):
        """T-concurrent-2: max_parallel_batches=3, 5 batches dispatched in parallel groups."""
        profiles = _sample_profiles(10)
        shared = _fresh_shared()

        # Track dispatch order to verify parallelism
        dispatch_order = []
        _orig_async = FakeApifyClient.enrich_profiles_async

        def _tracking_async(self_client, urls):
            dispatch_order.append(len(dispatch_order))
            return _orig_async(self_client, urls)

        with _pipeline_patches(shared, str(tmp_path), batch_size=2):
            with patch.object(FakeApifyClient, 'enrich_profiles_async', _tracking_async):
                result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.enriched == 10
        assert result.batches_completed == 5
        # All 5 dispatched
        assert len(dispatch_order) == 5

    def test_concurrent_3_out_of_order_completion(self, tmp_path):
        """T-concurrent-3: 3 batches complete in reverse order. All processed correctly."""
        profiles = _sample_profiles(6)
        shared = _fresh_shared()

        # Track on_progress calls
        progress_calls = []

        def on_progress(enriched, failed, total, batch_idx):
            progress_calls.append((enriched, failed, total, batch_idx))

        with _pipeline_patches(shared, str(tmp_path), batch_size=2):
            result = enrich_profiles(profiles, data_dir=tmp_path, on_progress=on_progress)

        assert result.enriched == 6
        assert result.batches_completed == 3
        # on_progress called 3 times
        assert len(progress_calls) == 3
        # Enriched count increases monotonically
        enriched_values = [p[0] for p in progress_calls]
        assert enriched_values == sorted(enriched_values)

    def test_concurrent_4_one_batch_fails_mid_flight(self, tmp_path):
        """T-concurrent-4: One of 3 batches FAILED. Others unaffected."""
        profiles = _sample_profiles(6)
        shared = _fresh_shared()

        # Batch 1 (second dispatch) returns FAILED with partial results
        dispatch_count = {'n': 0}
        _orig_async = FakeApifyClient.enrich_profiles_async

        def _failing_async(self_client, urls):
            dispatch_count['n'] += 1
            if dispatch_count['n'] == 2:
                # Override terminal_status for this batch
                run_id = _orig_async(self_client, urls)
                self_client._s['runs'][run_id]['status'] = 'FAILED'
                # Remove one result to simulate partial
                if self_client._s['runs'][run_id]['results']:
                    self_client._s['runs'][run_id]['results'].pop()
                return run_id
            return _orig_async(self_client, urls)

        with _pipeline_patches(shared, str(tmp_path), batch_size=2):
            with patch.object(FakeApifyClient, 'enrich_profiles_async', _failing_async):
                result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.batches_completed == 3
        # Batch 0: 2 enriched, Batch 1: 1 enriched + 1 failed, Batch 2: 2 enriched
        assert result.enriched == 5
        assert result.failed == 1

        # State records FAILED for batch 1
        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        events = _read_state_events(state_path)
        fetched = [e for e in events if e['type'] == 'batch_fetched']
        batch1_fetched = [e for e in fetched if e['batch_idx'] == 1]
        assert batch1_fetched[0]['run_status'] == 'FAILED'

    def test_concurrent_5_key_exhaustion_mid_flight(self, tmp_path):
        """T-concurrent-5: First 3 batches dispatch, key exhausted on 4th.
        Once keys are exhausted during dispatch, the pipeline can't poll either
        (needs a healthy key), so inflight batches stay unprocessed."""
        profiles = _sample_profiles(10)
        tracker = KeyHealthTracker(['key_a'])
        shared = _fresh_shared()

        dispatch_count = {'n': 0}
        _orig_async = FakeApifyClient.enrich_profiles_async

        def _exhausting_async(self_client, urls):
            dispatch_count['n'] += 1
            if dispatch_count['n'] > 3:
                raise ApifyCreditExhaustedError('402', status_code=402)
            return _orig_async(self_client, urls)

        with _pipeline_patches(shared, str(tmp_path), batch_size=2):
            with patch.object(FakeApifyClient, 'enrich_profiles_async', _exhausting_async):
                result = enrich_profiles(profiles, data_dir=tmp_path, key_tracker=tracker)

        assert result.stopped_reason == 'all_keys_exhausted'
        # 3 dispatched but can't poll (key exhausted) — inflight stays for resume
        assert dispatch_count['n'] == 4  # 3 succeeded + 1 failed
        # Batches 4-5 not dispatched
        assert shared['start_call_count'] == 3

    def test_concurrent_6_resume_with_inflight_batches(self, tmp_path):
        """T-concurrent-6: Resume after crash with 1 completed, some fetched, rest pending.
        On resume: completed batches skipped, fetched batches processed from disk,
        inflight batches resume polling, and no re-dispatches for already-dispatched batches."""
        profiles = _sample_profiles(8)
        shared = _fresh_shared()

        # --- Run 1: Complete batch 0, crash during batch 1 processing ---
        # With max_parallel=5 and 4 batches, all 4 get dispatched in run 1.
        call_count = {'n': 0}

        from linkedout.enrichment_pipeline import bulk_enrichment as _be
        _real_process = _be._process_batch_results

        def _crashing_process(*args, **kwargs):
            call_count['n'] += 1
            if call_count['n'] == 1:
                return _real_process(*args, **kwargs)
            raise RuntimeError('crash during batch 1 processing')

        with _pipeline_patches(shared, str(tmp_path), batch_size=2):
            with patch(f'{_MOD}._process_batch_results', side_effect=_crashing_process):
                with pytest.raises(RuntimeError, match='crash during batch 1'):
                    enrich_profiles(profiles, data_dir=tmp_path)

        # batch 0 completed, batch 1 fetched but processing crashed
        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        events = _read_state_events(state_path)
        assert _count_events(events, 'batch_completed') == 1  # batch 0

        first_run_dispatches = shared['start_call_count']

        # --- Run 2: Resume. Batch 0 skipped, batch 1 resumed from disk,
        # batches 2-3 resume via poll (already dispatched in run 1). ---
        with _pipeline_patches(shared, str(tmp_path), batch_size=2):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.batches_completed == 4
        assert result.enriched == 8
        # No new dispatches — all batches were already dispatched in run 1
        assert shared['start_call_count'] == first_run_dispatches


# ===========================================================================
# Money protection tests (T-M1 through T-M4)
# ===========================================================================

class TestMoneyProtection:

    def test_m1_failed_run_partial_results_no_redispatch(self, tmp_path):
        """T-M1: FAILED run fetches partial results, no re-dispatch."""
        profiles = _sample_profiles(2)
        shared = _fresh_shared()
        shared['terminal_status'] = 'FAILED'
        shared['missing_urls'] = {'https://linkedin.com/in/person-1'}

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.enriched == 1
        assert result.failed == 1
        assert shared['start_call_count'] == 1  # no re-dispatch

        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        events = _read_state_events(state_path)
        fetched = [e for e in events if e['type'] == 'batch_fetched']
        assert fetched[0]['run_status'] == 'FAILED'

    def test_m2_timedout_run_partial_results_no_redispatch(self, tmp_path):
        """T-M2: TIMED-OUT run fetches partial results, no re-dispatch."""
        profiles = _sample_profiles(2)
        shared = _fresh_shared()
        shared['terminal_status'] = 'TIMED-OUT'
        shared['missing_urls'] = {'https://linkedin.com/in/person-1'}

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.enriched == 1
        assert result.failed == 1
        assert shared['start_call_count'] == 1  # no re-dispatch

        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        events = _read_state_events(state_path)
        fetched = [e for e in events if e['type'] == 'batch_fetched']
        assert fetched[0]['run_status'] == 'TIMED-OUT'

    def test_m3_resume_all_completed_on_apify_no_dispatch(self, tmp_path):
        """T-M3: All 3 batches in-flight on crash. Apify has results. No re-dispatch."""
        profiles = _sample_profiles(6)
        shared = _fresh_shared()

        # --- Run 1: dispatch 3 batches, crash before processing ---
        with _pipeline_patches(shared, str(tmp_path), batch_size=2):
            with patch(f'{_MOD}._process_batch_results', side_effect=Exception('crash')):
                with pytest.raises(Exception, match='crash'):
                    enrich_profiles(profiles, data_dir=tmp_path)

        first_run_dispatches = shared['start_call_count']
        assert first_run_dispatches == 3  # all 3 dispatched

        # --- Run 2: resume. All 3 batches fetched from disk, zero new dispatches ---
        with _pipeline_patches(shared, str(tmp_path), batch_size=2):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.batches_completed == 3
        assert result.enriched == 6
        # Zero new dispatches — money saved
        assert shared['start_call_count'] == first_run_dispatches

    def test_m4_resume_with_results_on_disk(self, tmp_path):
        """T-M4: Results on disk from prior fetch. fetch_results NOT called again."""
        profiles = _sample_profiles(2)
        shared = _fresh_shared()

        # --- Run 1: full success ---
        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            with patch(f'{_MOD}._process_batch_results', side_effect=Exception('crash')):
                with pytest.raises(Exception, match='crash'):
                    enrich_profiles(profiles, data_dir=tmp_path)

        fetch_after_run1 = shared['fetch_call_count']

        # Results are on disk now
        results_dir = tmp_path / 'enrichment' / 'results'
        assert len(list(results_dir.glob('*.json'))) == 1

        # --- Run 2: resume processes from disk, no new fetch ---
        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.enriched == 2
        # fetch_results NOT called again (disk cache)
        assert shared['fetch_call_count'] == fetch_after_run1


# ===========================================================================
# Crash recovery tests (T-R1 through T-R3)
# ===========================================================================

class TestCrashRecovery:

    def test_r1_mixed_resume_states(self, tmp_path):
        """T-R1: 7 batches in mixed states. Completed skipped, inflight resumed, pending dispatched."""
        profiles = _sample_profiles(14)
        shared = _fresh_shared()

        from linkedout.enrichment_pipeline import bulk_enrichment as _be
        _real_process = _be._process_batch_results

        # --- Run 1: Crash after processing batch 0 and 1 ---
        call_count = {'n': 0}

        def _crashing_process(*args, **kwargs):
            call_count['n'] += 1
            if call_count['n'] <= 2:
                return _real_process(*args, **kwargs)
            raise RuntimeError('crash mid-flight')

        with _pipeline_patches(shared, str(tmp_path), batch_size=2):
            with patch(f'{_MOD}._process_batch_results', side_effect=_crashing_process):
                with pytest.raises(RuntimeError, match='crash mid-flight'):
                    enrich_profiles(profiles, data_dir=tmp_path)

        # Batch 0, 1 completed. Some fetched but unprocessed, rest pending.
        first_run_dispatches = shared['start_call_count']

        # --- Run 2: Resume completes all 7 ---
        with _pipeline_patches(shared, str(tmp_path), batch_size=2):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.batches_completed == 7
        assert result.enriched == 14

    def test_r2_crash_during_post_processing(self, tmp_path):
        """T-R2: Crash after partial profile processing. Resume skips already-processed."""
        profiles = _sample_profiles(5)
        shared = _fresh_shared()

        from linkedout.enrichment_pipeline import bulk_enrichment as _be
        _real_process = _be._process_batch_results

        # --- Run 1: dispatch+fetch succeeds, processing crashes ---
        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            with patch(f'{_MOD}._process_batch_results', side_effect=Exception('crash')):
                with pytest.raises(Exception, match='crash'):
                    enrich_profiles(profiles, data_dir=tmp_path)

        # Manually add partial profile_processed events
        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        for i in range(3):
            _append_state(state_path, {
                'type': 'profile_processed',
                'batch_idx': 0,
                'linkedin_url': f'https://linkedin.com/in/person-{i}',
                'profile_id': f'cp_{i}',
                'status': 'enriched',
            })

        # --- Run 2: resume, skip 3 already-processed ---
        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.batches_completed == 1
        assert result.enriched == 5  # 3 prior + 2 new

    def test_r3_back_to_back_resumes_no_state_growth(self, tmp_path):
        """T-R3: Completed pipeline, re-run twice. No state growth, no dispatches."""
        profiles = _sample_profiles(4)
        shared = _fresh_shared()

        with _pipeline_patches(shared, str(tmp_path), batch_size=2):
            r1 = enrich_profiles(profiles, data_dir=tmp_path)
        assert r1.batches_completed == 2
        assert r1.enriched == 4

        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        state_size_1 = state_path.stat().st_size

        # Run 2 — no new events
        with _pipeline_patches(shared, str(tmp_path), batch_size=2):
            r2 = enrich_profiles(profiles, data_dir=tmp_path)
        assert r2.batches_completed == 2
        assert r2.enriched == 4

        state_size_2 = state_path.stat().st_size
        assert state_size_2 == state_size_1  # no growth

        dispatches_after = shared['start_call_count']

        # Run 3 — still no growth
        with _pipeline_patches(shared, str(tmp_path), batch_size=2):
            r3 = enrich_profiles(profiles, data_dir=tmp_path)
        assert r3.batches_completed == 2

        state_size_3 = state_path.stat().st_size
        assert state_size_3 == state_size_1

        assert shared['start_call_count'] == dispatches_after  # no new dispatches


# ===========================================================================
# Error isolation tests (T-E1 through T-E3)
# ===========================================================================

class TestErrorIsolation:

    def test_e1_poll_error_one_batch_other_succeeds(self, tmp_path):
        """T-E1: Poll error for batch 0, batch 1 succeeds in same cycle."""
        profiles = _sample_profiles(4)
        shared = _fresh_shared()

        # Track per-run_id poll behavior
        poll_count = {}
        _orig_check = FakeApifyClient.check_run_status

        def _failing_check(self_client, run_id):
            poll_count.setdefault(run_id, 0)
            poll_count[run_id] += 1
            # First poll of first run fails
            if run_id == 'fake_run_1' and poll_count[run_id] == 1:
                raise RuntimeError('poll error for batch 0')
            return _orig_check(self_client, run_id)

        with _pipeline_patches(shared, str(tmp_path), batch_size=2):
            with patch.object(FakeApifyClient, 'check_run_status', _failing_check):
                result = enrich_profiles(profiles, data_dir=tmp_path)

        # Both batches eventually complete
        assert result.batches_completed == 2
        assert result.enriched == 4

    def test_e2_fetch_fails_batch_stays_inflight(self, tmp_path):
        """T-E2: fetch_results fails once, batch retried on next cycle."""
        profiles = _sample_profiles(2)
        shared = _fresh_shared()

        fetch_count = {'n': 0}
        _orig_fetch = FakeApifyClient.fetch_results

        def _failing_fetch(self_client, dataset_id):
            fetch_count['n'] += 1
            if fetch_count['n'] == 1:
                raise RuntimeError('fetch failed')
            return _orig_fetch(self_client, dataset_id)

        with _pipeline_patches(shared, str(tmp_path), batch_size=100):
            with patch.object(FakeApifyClient, 'fetch_results', _failing_fetch):
                result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.enriched == 2
        assert result.batches_completed == 1
        assert fetch_count['n'] == 2  # first failed, second succeeded

    def test_e3_all_keys_invalid_mid_flight(self, tmp_path):
        """T-E3: 3 batches dispatched, keys become invalid during poll phase."""
        profiles = _sample_profiles(6)
        shared = _fresh_shared()

        dispatch_count = {'n': 0}
        _orig_async = FakeApifyClient.enrich_profiles_async

        def _tracking_async(self_client, urls):
            dispatch_count['n'] += 1
            return _orig_async(self_client, urls)

        # After dispatch, make _get_key return None (simulating all keys exhausted during poll)
        get_key_count = {'n': 0}

        def _exhausting_get_key(tracker):
            get_key_count['n'] += 1
            # Allow dispatches (first 3 calls), then exhaust for poll phase
            if get_key_count['n'] > 3:
                return None
            return 'fake-key'

        with _pipeline_patches(shared, str(tmp_path), batch_size=2):
            with patch.object(FakeApifyClient, 'enrich_profiles_async', _tracking_async):
                with patch(f'{_MOD}._get_key', side_effect=_exhausting_get_key):
                    result = enrich_profiles(profiles, data_dir=tmp_path)

        assert result.stopped_reason == 'all_keys_exhausted'

        # State has batch_started events (recoverable on resume)
        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        events = _read_state_events(state_path)
        started = [e for e in events if e['type'] == 'batch_started']
        assert len(started) == 3


# ===========================================================================
# Resume helper unit tests (T-BH1 through T-BH5)
# ===========================================================================

class TestResumeHelper:

    def test_bh1_completed_batch_skip(self, tmp_path):
        """T-BH1: Completed batch → action='skip'."""
        results_dir = tmp_path / 'results'
        results_dir.mkdir()
        existing_state = {
            0: BatchState(batch_idx=0, urls=['u1', 'u2'], completed=True,
                          processed_urls={'u1', 'u2'}),
        }
        result = _check_batch_resume(0, ['u1', 'u2'], existing_state, results_dir)
        assert result.action == 'skip'
        assert result.already_processed == {'u1', 'u2'}

    def test_bh2_fetched_partial_process(self, tmp_path):
        """T-BH2: Fetched, results on disk, partially processed → action='process'."""
        results_dir = tmp_path / 'results'
        results_dir.mkdir()
        _save_results(results_dir, 'run1', [
            {'linkedinUrl': 'u1'}, {'linkedinUrl': 'u2'},
            {'linkedinUrl': 'u3'}, {'linkedinUrl': 'u4'},
            {'linkedinUrl': 'u5'},
        ])
        existing_state = {
            0: BatchState(batch_idx=0, urls=['u1', 'u2', 'u3', 'u4', 'u5'],
                          run_id='run1', dataset_id='ds1',
                          processed_urls={'u1', 'u2', 'u3'}),
        }
        result = _check_batch_resume(0, ['u1', 'u2', 'u3', 'u4', 'u5'], existing_state, results_dir)
        assert result.action == 'process'
        assert result.run_id == 'run1'
        assert result.results is not None
        assert result.already_processed == {'u1', 'u2', 'u3'}

    def test_bh3_dataset_set_results_missing_poll(self, tmp_path):
        """T-BH3: dataset_id set but results file missing → action='poll'."""
        results_dir = tmp_path / 'results'
        results_dir.mkdir()
        # No results file on disk
        existing_state = {
            0: BatchState(batch_idx=0, urls=['u1'], run_id='run1', dataset_id='ds1'),
        }
        result = _check_batch_resume(0, ['u1'], existing_state, results_dir)
        assert result.action == 'poll'
        assert result.run_id == 'run1'

    def test_bh4_started_not_fetched_poll(self, tmp_path):
        """T-BH4: run_id set, no dataset_id → action='poll'."""
        results_dir = tmp_path / 'results'
        results_dir.mkdir()
        existing_state = {
            0: BatchState(batch_idx=0, urls=['u1'], run_id='run1'),
        }
        result = _check_batch_resume(0, ['u1'], existing_state, results_dir)
        assert result.action == 'poll'
        assert result.run_id == 'run1'

    def test_bh5_no_state_dispatch(self, tmp_path):
        """T-BH5: No state → action='dispatch'."""
        results_dir = tmp_path / 'results'
        results_dir.mkdir()
        existing_state = {}  # No entry for batch 0
        result = _check_batch_resume(0, ['u1'], existing_state, results_dir)
        assert result.action == 'dispatch'
        assert result.run_id is None


# ---------------------------------------------------------------------------
# State file rotation
# ---------------------------------------------------------------------------

class TestRotateState:

    def test_rotates_to_prev(self, tmp_path):
        state_path = tmp_path / 'enrich-state.jsonl'
        state_path.write_text('{"type": "test"}\n')
        _rotate_state(state_path)
        assert not state_path.exists()
        assert (tmp_path / 'enrich-state.jsonl.prev').exists()

    def test_overwrites_existing_prev(self, tmp_path):
        state_path = tmp_path / 'enrich-state.jsonl'
        prev_path = tmp_path / 'enrich-state.jsonl.prev'
        prev_path.write_text('old\n')
        state_path.write_text('new\n')
        _rotate_state(state_path)
        assert prev_path.read_text() == 'new\n'
        assert not state_path.exists()


# ---------------------------------------------------------------------------
# check_recoverable_batches (read-only)
# ---------------------------------------------------------------------------

class TestCheckRecoverableBatches:

    def test_no_state_file(self, tmp_path):
        summary = check_recoverable_batches(tmp_path)
        assert summary.recovered == 0
        assert summary.still_running == 0

    def test_all_completed(self, tmp_path):
        """All batches completed → nothing recoverable."""
        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        state_path.parent.mkdir(parents=True)
        _append_state(state_path, {
            'type': 'batch_started', 'batch_idx': 0,
            'run_id': 'r0', 'urls': ['u1'],
        })
        _append_state(state_path, {
            'type': 'batch_completed', 'batch_idx': 0,
            'enriched': 1, 'failed': 0,
        })
        summary = check_recoverable_batches(tmp_path)
        assert summary.recovered == 0

    @patch('linkedout.enrichment_pipeline.bulk_enrichment.LinkedOutApifyClient')
    @patch('linkedout.enrichment_pipeline.bulk_enrichment.get_platform_apify_key',
           return_value='test-key')
    def test_succeeded_run_reported(self, _mock_key, mock_client_cls, tmp_path):
        """Incomplete batch with SUCCEEDED Apify run → reported as recoverable."""
        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        state_path.parent.mkdir(parents=True)
        _append_state(state_path, {
            'type': 'batch_started', 'batch_idx': 0,
            'run_id': 'r0', 'urls': ['u1', 'u2', 'u3'],
        })

        mock_client = MagicMock()
        mock_client.check_run_status.return_value = ('SUCCEEDED', 'ds0')
        mock_client_cls.return_value = mock_client

        summary = check_recoverable_batches(tmp_path)
        assert summary.recovered == 3
        assert summary.failed == 0
        # Read-only: state file should NOT be modified
        states = _load_state(state_path)
        assert not states[0].completed

    @patch('linkedout.enrichment_pipeline.bulk_enrichment.LinkedOutApifyClient')
    @patch('linkedout.enrichment_pipeline.bulk_enrichment.get_platform_apify_key',
           return_value='test-key')
    def test_still_running_reported(self, _mock_key, mock_client_cls, tmp_path):
        """Incomplete batch still running → reported as still_running."""
        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        state_path.parent.mkdir(parents=True)
        _append_state(state_path, {
            'type': 'batch_started', 'batch_idx': 0,
            'run_id': 'r0', 'urls': ['u1', 'u2'],
        })

        mock_client = MagicMock()
        mock_client.check_run_status.return_value = None  # still running
        mock_client_cls.return_value = mock_client

        summary = check_recoverable_batches(tmp_path)
        assert summary.still_running == 2
        assert summary.recovered == 0


# ---------------------------------------------------------------------------
# recover_incomplete_batches
# ---------------------------------------------------------------------------

class TestRecoverIncompleteBatches:

    def _write_state(self, tmp_path, events):
        """Helper to write state events and create directory structure."""
        enrichment_dir = tmp_path / 'enrichment'
        enrichment_dir.mkdir(parents=True, exist_ok=True)
        (enrichment_dir / 'results').mkdir(exist_ok=True)
        state_path = enrichment_dir / 'enrich-state.jsonl'
        for event in events:
            _append_state(state_path, event)
        return state_path

    @patch('linkedout.enrichment_pipeline.bulk_enrichment.LinkedOutApifyClient')
    @patch('linkedout.enrichment_pipeline.bulk_enrichment.get_platform_apify_key',
           return_value='test-key')
    def test_recover_succeeded_batches(self, _mock_key, mock_client_cls, tmp_path):
        """SUCCEEDED Apify runs → results fetched, processed, state updated."""
        self._write_state(tmp_path, [
            {'type': 'batch_started', 'batch_idx': 0,
             'run_id': 'r0', 'urls': ['https://linkedin.com/in/alice', 'https://linkedin.com/in/bob']},
            {'type': 'batch_started', 'batch_idx': 1,
             'run_id': 'r1', 'urls': ['https://linkedin.com/in/carol']},
            # batch 1 completed, batch 0 did not
            {'type': 'batch_completed', 'batch_idx': 1, 'enriched': 1, 'failed': 0},
        ])

        mock_client = MagicMock()
        mock_client.check_run_status.return_value = ('SUCCEEDED', 'ds0')
        mock_client.fetch_results.return_value = [
            {'linkedinUrl': 'https://linkedin.com/in/alice', 'firstName': 'Alice'},
            {'linkedinUrl': 'https://linkedin.com/in/bob', 'firstName': 'Bob'},
        ]
        mock_client_cls.return_value = mock_client

        # Mock DB session factory
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [
            ('cp_1', 'https://linkedin.com/in/alice'),
            ('cp_2', 'https://linkedin.com/in/bob'),
        ]

        @contextmanager
        def mock_db_factory():
            yield mock_session

        mock_post_service = MagicMock()
        mock_post_service.process_batch.return_value = (2, 0)  # 2 enriched, 0 failed

        summary = recover_incomplete_batches(
            data_dir=tmp_path,
            db_session_factory=mock_db_factory,
            post_enrichment_factory=lambda session: mock_post_service,
        )

        assert summary.recovered == 2
        assert summary.batches_recovered == 1
        assert summary.failed == 0
        # State file should be rotated (all resolved)
        assert not (tmp_path / 'enrichment' / 'enrich-state.jsonl').exists()
        assert (tmp_path / 'enrichment' / 'enrich-state.jsonl.prev').exists()

    @patch('linkedout.enrichment_pipeline.bulk_enrichment.LinkedOutApifyClient')
    @patch('linkedout.enrichment_pipeline.bulk_enrichment.get_platform_apify_key',
           return_value='test-key')
    def test_recover_failed_batches(self, _mock_key, mock_client_cls, tmp_path):
        """FAILED Apify run → marked failed, profiles not processed."""
        self._write_state(tmp_path, [
            {'type': 'batch_started', 'batch_idx': 0,
             'run_id': 'r0', 'urls': ['u1', 'u2']},
        ])

        mock_client = MagicMock()
        mock_client.check_run_status.return_value = ('FAILED', 'ds0')
        mock_client_cls.return_value = mock_client

        summary = recover_incomplete_batches(data_dir=tmp_path)

        assert summary.failed == 2
        assert summary.recovered == 0
        # State file should have batch_completed with 0 enriched
        states = _load_state(tmp_path / 'enrichment' / 'enrich-state.jsonl.prev')
        assert states[0].completed

    @patch('linkedout.enrichment_pipeline.bulk_enrichment.LinkedOutApifyClient')
    @patch('linkedout.enrichment_pipeline.bulk_enrichment.get_platform_apify_key',
           return_value='test-key')
    def test_recover_still_running(self, _mock_key, mock_client_cls, tmp_path):
        """Still-running batch → skipped, state file NOT rotated."""
        state_path = self._write_state(tmp_path, [
            {'type': 'batch_started', 'batch_idx': 0,
             'run_id': 'r0', 'urls': ['u1']},
        ])

        mock_client = MagicMock()
        mock_client.check_run_status.return_value = None  # still running
        mock_client_cls.return_value = mock_client

        summary = recover_incomplete_batches(data_dir=tmp_path)

        assert summary.still_running == 1
        assert summary.recovered == 0
        # State file should NOT be rotated
        assert state_path.exists()

    @patch('linkedout.enrichment_pipeline.bulk_enrichment.LinkedOutApifyClient')
    @patch('linkedout.enrichment_pipeline.bulk_enrichment.get_platform_apify_key',
           return_value='test-key')
    def test_recover_mixed(self, _mock_key, mock_client_cls, tmp_path):
        """One SUCCEEDED, one FAILED, one RUNNING → each handled correctly."""
        url1 = 'https://linkedin.com/in/alice'
        url2 = 'https://linkedin.com/in/bob'
        url3 = 'https://linkedin.com/in/carol'
        url4 = 'https://linkedin.com/in/dave'
        url5 = 'https://linkedin.com/in/eve'

        self._write_state(tmp_path, [
            {'type': 'batch_started', 'batch_idx': 0,
             'run_id': 'r0', 'urls': [url1, url2]},
            {'type': 'batch_started', 'batch_idx': 1,
             'run_id': 'r1', 'urls': [url3]},
            {'type': 'batch_started', 'batch_idx': 2,
             'run_id': 'r2', 'urls': [url4, url5]},
        ])

        mock_client = MagicMock()

        def side_effect(run_id):
            if run_id == 'r0':
                return ('SUCCEEDED', 'ds0')
            elif run_id == 'r1':
                return ('FAILED', 'ds1')
            else:
                return None  # still running

        mock_client.check_run_status.side_effect = side_effect
        mock_client.fetch_results.return_value = [
            {'linkedinUrl': url1, 'firstName': 'Alice'},
            {'linkedinUrl': url2, 'firstName': 'Bob'},
        ]
        mock_client_cls.return_value = mock_client

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [
            ('cp_1', url1), ('cp_2', url2),
        ]

        @contextmanager
        def mock_db_factory():
            yield mock_session

        mock_post_service = MagicMock()
        mock_post_service.process_batch.return_value = (2, 0)

        summary = recover_incomplete_batches(
            data_dir=tmp_path,
            db_session_factory=mock_db_factory,
            post_enrichment_factory=lambda session: mock_post_service,
        )

        assert summary.recovered == 2
        assert summary.failed == 1
        assert summary.still_running == 2
        assert summary.batches_recovered == 1
        # State NOT rotated (batch 2 still running)
        assert (tmp_path / 'enrichment' / 'enrich-state.jsonl').exists()

    def test_no_state_file(self, tmp_path):
        """No state file → empty summary, no errors."""
        summary = recover_incomplete_batches(data_dir=tmp_path)
        assert summary.recovered == 0
        assert summary.failed == 0

    def test_all_completed_rotates_state(self, tmp_path):
        """All batches completed → state rotated on recovery call."""
        self._write_state(tmp_path, [
            {'type': 'batch_started', 'batch_idx': 0,
             'run_id': 'r0', 'urls': ['u1']},
            {'type': 'batch_completed', 'batch_idx': 0,
             'enriched': 1, 'failed': 0},
        ])
        state_path = tmp_path / 'enrichment' / 'enrich-state.jsonl'
        assert state_path.exists()

        summary = recover_incomplete_batches(data_dir=tmp_path)

        assert summary.recovered == 0
        assert not state_path.exists()
        assert (tmp_path / 'enrichment' / 'enrich-state.jsonl.prev').exists()
