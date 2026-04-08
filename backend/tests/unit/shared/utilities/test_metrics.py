# SPDX-License-Identifier: Apache-2.0
"""Tests for the file-based metrics collection module."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from shared.utilities.metrics import (
    _get_metrics_dir,
    read_summary,
    record_metric,
    update_summary,
)


class TestGetMetricsDir:
    """Tests for _get_metrics_dir() directory resolution."""

    def test_env_override(self, tmp_path, monkeypatch):
        """LINKEDOUT_METRICS_DIR env var overrides the default path."""
        monkeypatch.setenv('LINKEDOUT_METRICS_DIR', str(tmp_path / 'custom'))
        assert _get_metrics_dir() == tmp_path / 'custom'

    def test_default_when_env_unset(self, monkeypatch):
        """Falls back to ~/linkedout-data/metrics/ when env is unset."""
        monkeypatch.delenv('LINKEDOUT_METRICS_DIR', raising=False)
        from pathlib import Path
        expected = Path.home() / 'linkedout-data' / 'metrics'
        assert _get_metrics_dir() == expected


class TestRecordMetric:
    """Tests for record_metric() — daily JSONL append."""

    def test_creates_daily_file(self, tmp_path):
        """record_metric creates a YYYY-MM-DD.jsonl file in daily/."""
        record_metric('profiles_imported', 3847, metrics_dir=tmp_path, source='csv')

        daily_dir = tmp_path / 'daily'
        assert daily_dir.exists()

        jsonl_files = list(daily_dir.glob('*.jsonl'))
        assert len(jsonl_files) == 1

        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        assert jsonl_files[0].name == f'{today}.jsonl'

    def test_jsonl_line_contains_required_fields(self, tmp_path):
        """Each JSONL line has ts, metric, value, and context keys."""
        record_metric('profiles_imported', 3847, metrics_dir=tmp_path, source='csv')

        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        filepath = tmp_path / 'daily' / f'{today}.jsonl'
        line = filepath.read_text().strip()
        record = json.loads(line)

        assert record['metric'] == 'profiles_imported'
        assert record['value'] == 3847
        assert record['source'] == 'csv'
        assert 'ts' in record

    def test_timestamp_is_iso8601_utc(self, tmp_path):
        """The ts field is a valid ISO 8601 UTC timestamp."""
        record_metric('test_metric', 1, metrics_dir=tmp_path)

        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        filepath = tmp_path / 'daily' / f'{today}.jsonl'
        record = json.loads(filepath.read_text().strip())

        parsed = datetime.fromisoformat(record['ts'])
        assert parsed.tzinfo is not None or record['ts'].endswith('+00:00') or record['ts'].endswith('Z')

    def test_multiple_calls_append_to_same_file(self, tmp_path):
        """Multiple record_metric() calls append to the same daily file."""
        record_metric('metric_a', 1, metrics_dir=tmp_path)
        record_metric('metric_b', 2, metrics_dir=tmp_path)
        record_metric('metric_c', 3, metrics_dir=tmp_path)

        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        filepath = tmp_path / 'daily' / f'{today}.jsonl'
        lines = [line for line in filepath.read_text().splitlines() if line.strip()]

        assert len(lines) == 3

        records = [json.loads(line) for line in lines]
        assert records[0]['metric'] == 'metric_a'
        assert records[1]['metric'] == 'metric_b'
        assert records[2]['metric'] == 'metric_c'

    def test_directory_auto_created(self, tmp_path):
        """daily/ subdirectory is created automatically on first write."""
        metrics_dir = tmp_path / 'brand_new'
        assert not metrics_dir.exists()

        record_metric('first_write', 42, metrics_dir=metrics_dir)

        assert (metrics_dir / 'daily').is_dir()

    def test_context_kwargs_included(self, tmp_path):
        """Arbitrary **context kwargs are written into the JSONL line."""
        record_metric(
            'enrichment_batch', 50,
            metrics_dir=tmp_path,
            provider='openai',
            duration_ms=1200,
            batch_id='b-001',
        )

        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        filepath = tmp_path / 'daily' / f'{today}.jsonl'
        record = json.loads(filepath.read_text().strip())

        assert record['provider'] == 'openai'
        assert record['duration_ms'] == 1200
        assert record['batch_id'] == 'b-001'

    def test_jsonl_is_human_readable_and_grepable(self, tmp_path):
        """JSONL output is a single line per record — grep-friendly."""
        record_metric('profiles_imported', 100, metrics_dir=tmp_path, source='csv')

        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        filepath = tmp_path / 'daily' / f'{today}.jsonl'
        content = filepath.read_text()

        # Exactly one line (plus trailing newline)
        lines = content.splitlines()
        assert len(lines) == 1
        assert 'profiles_imported' in lines[0]


class TestReadSummary:
    """Tests for read_summary() — rolling summary reader."""

    def test_returns_empty_dict_when_no_file(self, tmp_path):
        """read_summary() returns {} when summary.json doesn't exist."""
        result = read_summary(metrics_dir=tmp_path)
        assert result == {}

    def test_reads_existing_summary(self, tmp_path):
        """read_summary() returns the contents of summary.json."""
        summary_data = {'profiles_total': 5000, 'companies_total': 300}
        (tmp_path / 'summary.json').write_text(json.dumps(summary_data))

        result = read_summary(metrics_dir=tmp_path)
        assert result == summary_data


class TestUpdateSummary:
    """Tests for update_summary() — merge updates into summary.json."""

    def test_creates_summary_when_missing(self, tmp_path):
        """update_summary() creates summary.json if it doesn't exist."""
        result = update_summary({'profiles_total': 100}, metrics_dir=tmp_path)

        assert result == {'profiles_total': 100}
        assert (tmp_path / 'summary.json').exists()

        on_disk = json.loads((tmp_path / 'summary.json').read_text())
        assert on_disk == {'profiles_total': 100}

    def test_merges_into_existing(self, tmp_path):
        """update_summary() merges new keys into existing summary."""
        (tmp_path / 'summary.json').write_text(
            json.dumps({'profiles_total': 100, 'companies_total': 50})
        )

        result = update_summary({'profiles_total': 200, 'new_key': 'hello'}, metrics_dir=tmp_path)

        assert result == {'profiles_total': 200, 'companies_total': 50, 'new_key': 'hello'}

    def test_overwrites_matching_keys(self, tmp_path):
        """update_summary() overwrites values for existing keys."""
        (tmp_path / 'summary.json').write_text(json.dumps({'count': 1}))

        result = update_summary({'count': 99}, metrics_dir=tmp_path)
        assert result['count'] == 99

    def test_returns_merged_result(self, tmp_path):
        """update_summary() returns the full merged dict."""
        result = update_summary({'a': 1}, metrics_dir=tmp_path)
        result = update_summary({'b': 2}, metrics_dir=tmp_path)

        assert result == {'a': 1, 'b': 2}

    def test_directory_auto_created(self, tmp_path):
        """Metrics directory is created if it doesn't exist."""
        nested = tmp_path / 'deep' / 'metrics'
        assert not nested.exists()

        update_summary({'k': 'v'}, metrics_dir=nested)

        assert nested.is_dir()
        assert (nested / 'summary.json').exists()
