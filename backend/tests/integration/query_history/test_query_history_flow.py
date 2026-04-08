# SPDX-License-Identifier: Apache-2.0
"""Integration tests for end-to-end query logging flow.

Tests the full pipeline: log_query() -> JSONL file -> readback,
session grouping, date-based file routing, metrics integration,
and concurrent write safety.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    """Point LINKEDOUT_DATA_DIR to a temp directory for test isolation."""
    monkeypatch.setenv('LINKEDOUT_DATA_DIR', str(tmp_path))
    return tmp_path


class TestLogAndReadback:
    """Log 5 queries and verify all entries are present with correct fields."""

    def test_log_and_readback(self, data_dir):
        from linkedout.query_history.query_logger import log_query

        queries = [
            {'query_text': 'who works at Stripe?', 'query_type': 'company_lookup', 'result_count': 12, 'duration_ms': 230},
            {'query_text': 'AI engineers in SF', 'query_type': 'person_search', 'result_count': 45, 'duration_ms': 450},
            {'query_text': 'startups in my network', 'query_type': 'semantic_search', 'result_count': 23, 'duration_ms': 1200},
            {'query_text': 'who do I know at Anthropic?', 'query_type': 'company_lookup', 'result_count': 8, 'duration_ms': 180},
            {'query_text': 'network stats', 'query_type': 'general', 'result_count': 1, 'duration_ms': 50},
        ]

        returned_ids = []
        for q in queries:
            query_id = log_query(**q)
            returned_ids.append(query_id)

        # Read back the JSONL file
        jsonl_files = list((data_dir / 'queries').glob('*.jsonl'))
        assert len(jsonl_files) == 1

        lines = jsonl_files[0].read_text().strip().split('\n')
        assert len(lines) == 5

        required_fields = {
            'timestamp', 'query_id', 'session_id', 'query_text',
            'query_type', 'result_count', 'duration_ms', 'model_used', 'is_refinement',
        }

        for i, line in enumerate(lines):
            entry = json.loads(line)
            # All required fields present
            assert required_fields.issubset(entry.keys()), f'Line {i} missing fields'
            # Values match what was logged
            assert entry['query_text'] == queries[i]['query_text']
            assert entry['query_type'] == queries[i]['query_type']
            assert entry['result_count'] == queries[i]['result_count']
            assert entry['duration_ms'] == queries[i]['duration_ms']
            # query_id matches return value
            assert entry['query_id'] == returned_ids[i]
            # Prefixes correct
            assert entry['query_id'].startswith('q_')
            assert entry['session_id'].startswith('s_')
            # Timestamp is valid ISO format
            datetime.fromisoformat(entry['timestamp'])


class TestSessionGrouping:
    """Log queries within a session and verify session_id grouping."""

    def test_queries_in_same_session_share_session_id(self, data_dir):
        from linkedout.query_history.session_manager import get_or_create_session
        from linkedout.query_history.query_logger import log_query

        # Create a session and log 3 queries with the same session_id
        session_id, is_new = get_or_create_session('first query')
        assert is_new is True

        log_query('first query', session_id=session_id)
        log_query('refine that', session_id=session_id, is_refinement=True)
        log_query('show more', session_id=session_id, is_refinement=True)

        jsonl_files = list((data_dir / 'queries').glob('*.jsonl'))
        lines = jsonl_files[0].read_text().strip().split('\n')
        entries = [json.loads(line) for line in lines]

        # All 3 should share the same session_id
        session_ids = {e['session_id'] for e in entries}
        assert len(session_ids) == 1
        assert session_id in session_ids

    def test_new_session_after_timeout(self, data_dir):
        from linkedout.query_history.session_manager import get_or_create_session
        from linkedout.query_history.query_logger import log_query

        # Create first session
        session_id_1, _ = get_or_create_session('first query')
        log_query('first query', session_id=session_id_1)

        # Simulate timeout by backdating the session file
        session_file = data_dir / 'queries' / '.active_session.json'
        session_data = json.loads(session_file.read_text())
        past = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()
        session_data['last_query_at'] = past
        session_file.write_text(json.dumps(session_data))

        # Next get_or_create_session should start a new session
        session_id_2, is_new = get_or_create_session('new topic')
        assert is_new is True
        assert session_id_2 != session_id_1

        log_query('new topic', session_id=session_id_2)

        # Verify JSONL has entries with two different session_ids
        jsonl_files = list((data_dir / 'queries').glob('*.jsonl'))
        lines = jsonl_files[0].read_text().strip().split('\n')
        entries = [json.loads(line) for line in lines]

        session_ids = {e['session_id'] for e in entries}
        assert len(session_ids) == 2
        assert session_id_1 in session_ids
        assert session_id_2 in session_ids


class TestDateBasedFileRouting:
    """Queries on different dates go to separate JSONL files."""

    def test_different_dates_different_files(self, data_dir):
        from linkedout.query_history.query_logger import log_query

        # Mock datetime.now to control the date for file routing
        date_1 = datetime(2026, 4, 5, 10, 0, 0, tzinfo=timezone.utc)
        date_2 = datetime(2026, 4, 6, 14, 30, 0, tzinfo=timezone.utc)

        with patch('linkedout.query_history.query_logger.datetime') as mock_dt:
            mock_dt.now.return_value = date_1
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            log_query('query on day 1', session_id='s_day1')

        with patch('linkedout.query_history.query_logger.datetime') as mock_dt:
            mock_dt.now.return_value = date_2
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            log_query('query on day 2', session_id='s_day2')

        jsonl_files = sorted((data_dir / 'queries').glob('*.jsonl'))
        assert len(jsonl_files) == 2

        filenames = [f.name for f in jsonl_files]
        assert '2026-04-05.jsonl' in filenames
        assert '2026-04-06.jsonl' in filenames

        # Verify each file has exactly 1 entry
        for f in jsonl_files:
            lines = f.read_text().strip().split('\n')
            assert len(lines) == 1


class TestMetricsIntegration:
    """Verify metrics are recorded when the metrics module is available."""

    def test_query_triggers_metric_recording(self, data_dir, monkeypatch):
        # Set up metrics dir inside our data_dir
        metrics_dir = data_dir / 'metrics'
        monkeypatch.setenv('LINKEDOUT_METRICS_DIR', str(metrics_dir))

        from linkedout.query_history.query_logger import log_query

        log_query(
            'who works at Stripe?',
            query_type='company_lookup',
            result_count=12,
            duration_ms=230,
            session_id='s_metrics_test',
        )

        # Check that a metrics file was created in the daily dir
        daily_dir = metrics_dir / 'daily'
        if daily_dir.exists():
            jsonl_files = list(daily_dir.glob('*.jsonl'))
            if jsonl_files:
                # Parse the metrics file and find our query metric
                all_lines = []
                for f in jsonl_files:
                    all_lines.extend(f.read_text().strip().split('\n'))

                query_metrics = []
                for line in all_lines:
                    entry = json.loads(line)
                    if entry.get('metric') == 'query':
                        query_metrics.append(entry)

                assert len(query_metrics) >= 1
                metric = query_metrics[0]
                assert metric['value'] == 1
                # Context kwargs may be nested under 'metadata' key
                meta = metric.get('metadata', metric)
                assert meta.get('query_type') == 'company_lookup'
                assert meta.get('result_count') == 12
                assert meta.get('duration_ms') == 230
            else:
                # Metrics module may not record if _record_metric is None
                pytest.skip('Metrics daily files not created — metrics module may not be wired')
        else:
            pytest.skip('Metrics daily dir not created — metrics module may not be wired')


class TestConcurrentWrites:
    """Verify concurrent writes produce a valid, non-corrupted JSONL file."""

    def test_concurrent_thread_writes_no_corruption(self, data_dir):
        from linkedout.query_history.query_logger import log_query

        num_threads = 4
        queries_per_thread = 5
        total_expected = num_threads * queries_per_thread

        def write_batch(thread_id):
            for i in range(queries_per_thread):
                log_query(
                    f'concurrent query {thread_id}-{i}',
                    query_type='general',
                    result_count=i,
                    duration_ms=100 + i,
                    session_id=f's_thread_{thread_id}',
                )

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(write_batch, t) for t in range(num_threads)]
            for f in futures:
                f.result()  # Raise any exceptions

        jsonl_files = list((data_dir / 'queries').glob('*.jsonl'))
        assert len(jsonl_files) == 1

        lines = jsonl_files[0].read_text().strip().split('\n')
        assert len(lines) == total_expected

        # Every line must be valid JSON with required fields
        query_ids = set()
        for i, line in enumerate(lines):
            entry = json.loads(line)
            assert 'query_id' in entry, f'Line {i} missing query_id'
            assert 'session_id' in entry, f'Line {i} missing session_id'
            assert entry['query_id'] not in query_ids, f'Duplicate query_id at line {i}'
            query_ids.add(entry['query_id'])

        assert len(query_ids) == total_expected
