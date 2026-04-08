# SPDX-License-Identifier: Apache-2.0
"""Tests for linkedout.query_history.query_logger — JSONL query logging."""

import json
import multiprocessing
import threading

import pytest


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    """Point LINKEDOUT_DATA_DIR to a temp directory."""
    monkeypatch.setenv('LINKEDOUT_DATA_DIR', str(tmp_path))
    return tmp_path


class TestLogQueryEntry:
    """log_query() produces a valid JSONL entry with all required fields."""

    def test_jsonl_entry_contains_all_required_fields(self, data_dir):
        from linkedout.query_history.query_logger import log_query

        log_query('who works at Stripe?', query_type='company_lookup', result_count=12, duration_ms=230)

        jsonl_files = list((data_dir / 'queries').glob('*.jsonl'))
        assert len(jsonl_files) == 1

        line = jsonl_files[0].read_text().strip().split('\n')[0]
        entry = json.loads(line)

        required_fields = {
            'timestamp', 'query_id', 'session_id', 'query_text',
            'query_type', 'result_count', 'duration_ms', 'model_used', 'is_refinement',
        }
        assert required_fields.issubset(entry.keys())

    def test_entry_values_match_arguments(self, data_dir):
        from linkedout.query_history.query_logger import log_query

        log_query(
            'who works at Stripe?',
            query_type='company_lookup',
            result_count=12,
            duration_ms=230,
            model_used='gpt-4',
            is_refinement=True,
        )

        jsonl_files = list((data_dir / 'queries').glob('*.jsonl'))
        entry = json.loads(jsonl_files[0].read_text().strip().split('\n')[0])

        assert entry['query_text'] == 'who works at Stripe?'
        assert entry['query_type'] == 'company_lookup'
        assert entry['result_count'] == 12
        assert entry['duration_ms'] == 230
        assert entry['model_used'] == 'gpt-4'
        assert entry['is_refinement'] is True


class TestLogQueryFilePath:
    """log_query() writes to the correct date-based JSONL file."""

    def test_file_created_in_date_based_path(self, data_dir):
        from linkedout.query_history.query_logger import log_query

        log_query('test query')

        jsonl_files = list((data_dir / 'queries').glob('*.jsonl'))
        assert len(jsonl_files) == 1
        # Filename should be YYYY-MM-DD.jsonl
        name = jsonl_files[0].name
        assert name.endswith('.jsonl')
        parts = name.replace('.jsonl', '').split('-')
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


class TestLogQueryId:
    """query_id has q_ prefix."""

    def test_query_id_has_q_prefix(self, data_dir):
        from linkedout.query_history.query_logger import log_query

        query_id = log_query('test query')
        assert query_id.startswith('q_')

    def test_query_id_matches_jsonl_entry(self, data_dir):
        from linkedout.query_history.query_logger import log_query

        query_id = log_query('test query')

        jsonl_files = list((data_dir / 'queries').glob('*.jsonl'))
        entry = json.loads(jsonl_files[0].read_text().strip().split('\n')[0])
        assert entry['query_id'] == query_id


class TestLogQuerySessionAutoCreate:
    """session_id is auto-generated when not provided."""

    def test_session_id_auto_generated(self, data_dir):
        from linkedout.query_history.query_logger import log_query

        log_query('test query')

        jsonl_files = list((data_dir / 'queries').glob('*.jsonl'))
        entry = json.loads(jsonl_files[0].read_text().strip().split('\n')[0])
        assert entry['session_id'].startswith('s_')

    def test_explicit_session_id_used(self, data_dir):
        from linkedout.query_history.query_logger import log_query

        log_query('test query', session_id='s_custom123')

        jsonl_files = list((data_dir / 'queries').glob('*.jsonl'))
        entry = json.loads(jsonl_files[0].read_text().strip().split('\n')[0])
        assert entry['session_id'] == 's_custom123'


class TestLogQueryDataDirOverride:
    """LINKEDOUT_DATA_DIR override changes output path."""

    def test_custom_data_dir(self, tmp_path, monkeypatch):
        custom_dir = tmp_path / 'custom-data'
        monkeypatch.setenv('LINKEDOUT_DATA_DIR', str(custom_dir))

        from linkedout.query_history.query_logger import log_query

        log_query('test query')

        jsonl_files = list((custom_dir / 'queries').glob('*.jsonl'))
        assert len(jsonl_files) == 1


class TestLogQueryConcurrentThreads:
    """Concurrent writes from threads don't corrupt the file."""

    def test_concurrent_thread_writes(self, data_dir):
        from linkedout.query_history.query_logger import log_query

        errors = []

        def write_entries(n):
            try:
                for i in range(50):
                    log_query(f'thread query {n}-{i}', session_id=f's_thread{n}')
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=write_entries, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f'Thread errors: {errors}'

        jsonl_files = list((data_dir / 'queries').glob('*.jsonl'))
        assert len(jsonl_files) == 1

        lines = jsonl_files[0].read_text().strip().split('\n')
        assert len(lines) == 200  # 4 threads * 50 entries

        # Every line must be valid JSON
        for i, line in enumerate(lines):
            entry = json.loads(line)
            assert 'query_id' in entry, f'Line {i} missing query_id'


def _worker_write_entries(args):
    """Worker function for multiprocessing test (must be top-level for pickling)."""
    data_dir_str, worker_id = args
    import os
    os.environ['LINKEDOUT_DATA_DIR'] = data_dir_str
    from linkedout.query_history.query_logger import log_query
    for i in range(50):
        log_query(f'process query {worker_id}-{i}', session_id=f's_proc{worker_id}')


class TestLogQueryConcurrentProcesses:
    """Concurrent writes from separate processes don't corrupt the file."""

    def test_concurrent_process_writes(self, data_dir):
        """Spawn 4 child processes each writing 50 entries, then verify all are valid JSON."""
        args = [(str(data_dir), i) for i in range(4)]

        with multiprocessing.Pool(processes=4) as pool:
            pool.map(_worker_write_entries, args)

        jsonl_files = list((data_dir / 'queries').glob('*.jsonl'))
        assert len(jsonl_files) == 1

        lines = jsonl_files[0].read_text().strip().split('\n')
        assert len(lines) == 200  # 4 processes * 50 entries

        # Every line must be valid JSON with no interleaving
        query_ids = set()
        for i, line in enumerate(lines):
            entry = json.loads(line)
            assert 'query_id' in entry, f'Line {i} missing query_id'
            assert entry['query_id'] not in query_ids, f'Duplicate query_id at line {i}'
            query_ids.add(entry['query_id'])


class TestLogQueryLazyDirectoryCreation:
    """Directory is created lazily on first write."""

    def test_directory_created_on_first_write(self, data_dir):
        queries_dir = data_dir / 'queries'
        assert not queries_dir.exists()

        from linkedout.query_history.query_logger import log_query

        log_query('test query')
        assert queries_dir.exists()
        assert queries_dir.is_dir()
