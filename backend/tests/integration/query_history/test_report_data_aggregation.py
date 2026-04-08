# SPDX-License-Identifier: Apache-2.0
"""Integration tests for report data aggregation.

Tests the data layer that the /linkedout-report skill aggregates over:
query activity counts, top searches extraction, network growth from
import reports, graceful degradation with missing data, and report persistence.

Since the report skill runs as inline bash/python within a skill template,
these tests verify the data files and aggregation patterns the skill relies on.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    """Point LINKEDOUT_DATA_DIR to a temp directory for test isolation."""
    monkeypatch.setenv('LINKEDOUT_DATA_DIR', str(tmp_path))
    return tmp_path


def _create_query_entries(queries_dir: Path, date_str: str, entries: list[dict]) -> None:
    """Write query entries to a date-based JSONL file."""
    queries_dir.mkdir(parents=True, exist_ok=True)
    jsonl_file = queries_dir / f'{date_str}.jsonl'
    with open(jsonl_file, 'a') as f:
        for entry in entries:
            f.write(json.dumps(entry) + '\n')


def _make_query_entry(
    query_text: str,
    query_type: str = 'general',
    result_count: int = 5,
    date_str: str = '2026-04-07',
    session_id: str = 's_test',
) -> dict:
    """Create a query entry dict matching the JSONL schema."""
    return {
        'timestamp': f'{date_str}T12:00:00+00:00',
        'query_id': f'q_test_{hash(query_text) % 100000}',
        'session_id': session_id,
        'query_text': query_text,
        'query_type': query_type,
        'result_count': result_count,
        'duration_ms': 200,
        'model_used': '',
        'is_refinement': False,
    }


class TestQueryActivityAggregation:
    """Verify query count aggregation across multiple data sources."""

    def test_total_query_count_across_files(self, data_dir):
        queries_dir = data_dir / 'queries'

        # Create 30 days of data with varying counts
        base_date = datetime(2026, 4, 7, tzinfo=timezone.utc)
        total_expected = 0
        for day_offset in range(30):
            date = base_date - timedelta(days=day_offset)
            date_str = date.strftime('%Y-%m-%d')
            count = (day_offset % 5) + 1  # 1-5 queries per day
            entries = [
                _make_query_entry(f'query {i} on {date_str}', date_str=date_str)
                for i in range(count)
            ]
            _create_query_entries(queries_dir, date_str, entries)
            total_expected += count

        # Count total lines across all JSONL files
        total_lines = 0
        for f in queries_dir.glob('*.jsonl'):
            total_lines += len(f.read_text().strip().split('\n'))

        assert total_lines == total_expected

    def test_weekly_count(self, data_dir):
        queries_dir = data_dir / 'queries'
        base_date = datetime(2026, 4, 7, tzinfo=timezone.utc)
        week_ago = base_date - timedelta(days=7)

        # 3 queries per day for 10 days
        for day_offset in range(10):
            date = base_date - timedelta(days=day_offset)
            date_str = date.strftime('%Y-%m-%d')
            entries = [
                _make_query_entry(f'query {i}', date_str=date_str)
                for i in range(3)
            ]
            _create_query_entries(queries_dir, date_str, entries)

        # Count queries in last 7 days (inclusive of week_ago)
        weekly_count = 0
        for f in queries_dir.glob('*.jsonl'):
            file_date = f.stem  # YYYY-MM-DD
            if file_date >= week_ago.strftime('%Y-%m-%d'):
                weekly_count += len(f.read_text().strip().split('\n'))

        # Days 0-7 inclusive = 8 days * 3 = 24
        assert weekly_count == 24

    def test_daily_average(self, data_dir):
        queries_dir = data_dir / 'queries'
        base_date = datetime(2026, 4, 7, tzinfo=timezone.utc)

        # 2 queries per day for 30 days = total 60, avg 2.0/day
        for day_offset in range(30):
            date = base_date - timedelta(days=day_offset)
            date_str = date.strftime('%Y-%m-%d')
            entries = [
                _make_query_entry(f'query {i}', date_str=date_str)
                for i in range(2)
            ]
            _create_query_entries(queries_dir, date_str, entries)

        total = sum(
            len(f.read_text().strip().split('\n'))
            for f in queries_dir.glob('*.jsonl')
        )
        avg_per_day = total / 30
        assert avg_per_day == pytest.approx(2.0)


class TestTopSearchesExtraction:
    """Verify top companies/topics extraction from query patterns."""

    def test_query_type_distribution(self, data_dir):
        queries_dir = data_dir / 'queries'
        entries = [
            _make_query_entry('who works at Stripe?', query_type='company_lookup'),
            _make_query_entry('engineers at Stripe', query_type='company_lookup'),
            _make_query_entry('AI startups', query_type='semantic_search'),
            _make_query_entry('network overview', query_type='general'),
            _make_query_entry('people at Anthropic', query_type='company_lookup'),
        ]
        _create_query_entries(queries_dir, '2026-04-07', entries)

        # Parse and count query types
        type_counts: dict[str, int] = {}
        for f in queries_dir.glob('*.jsonl'):
            for line in f.read_text().strip().split('\n'):
                entry = json.loads(line)
                qt = entry.get('query_type', 'general')
                type_counts[qt] = type_counts.get(qt, 0) + 1

        assert type_counts['company_lookup'] == 3
        assert type_counts['semantic_search'] == 1
        assert type_counts['general'] == 1

    def test_company_mention_extraction(self, data_dir):
        queries_dir = data_dir / 'queries'
        entries = [
            _make_query_entry('who works at Stripe?'),
            _make_query_entry('connections at Stripe'),
            _make_query_entry('people at Anthropic'),
            _make_query_entry('who do I know at OpenAI?'),
            _make_query_entry('engineers at Stripe'),
        ]
        _create_query_entries(queries_dir, '2026-04-07', entries)

        # Extract company mentions using the "at [Company]" pattern
        import re
        company_counts: dict[str, int] = {}
        for f in queries_dir.glob('*.jsonl'):
            for line in f.read_text().strip().split('\n'):
                entry = json.loads(line)
                text = entry['query_text']
                matches = re.findall(r'\bat\s+(\w+)', text, re.IGNORECASE)
                for m in matches:
                    if m.lower() not in ('the', 'my', 'a', 'an'):
                        company_counts[m] = company_counts.get(m, 0) + 1

        # Stripe should be most frequent (3 mentions via "at Stripe")
        assert 'Stripe' in company_counts
        assert company_counts['Stripe'] == 3
        assert 'Anthropic' in company_counts
        assert company_counts['Anthropic'] == 1
        assert 'OpenAI' in company_counts


class TestNetworkGrowthFromImportReports:
    """Verify network growth calculations from import-csv-*.json reports."""

    def test_import_report_parsing(self, data_dir):
        reports_dir = data_dir / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Create sample import reports
        report_1 = {
            'timestamp': '2026-03-15T10:00:00Z',
            'counts': {'succeeded': 1200, 'failed': 3, 'total': 1203},
        }
        report_2 = {
            'timestamp': '2026-04-07T14:00:00Z',
            'counts': {'succeeded': 3847, 'failed': 0, 'total': 3847},
        }

        (reports_dir / 'import-csv-20260315.json').write_text(json.dumps(report_1))
        (reports_dir / 'import-csv-20260407.json').write_text(json.dumps(report_2))

        # Parse import reports (same pattern as the skill)
        imports = []
        for f in sorted(reports_dir.glob('import-csv-*.json')):
            report = json.loads(f.read_text())
            ts = report.get('timestamp', 'unknown')
            counts = report.get('counts', {})
            total = counts.get('succeeded', counts.get('total', 0))
            imports.append({'date': ts[:10], 'count': total})

        assert len(imports) == 2
        assert imports[0]['date'] == '2026-03-15'
        assert imports[0]['count'] == 1200
        assert imports[1]['date'] == '2026-04-07'
        assert imports[1]['count'] == 3847

    def test_growth_calculation(self, data_dir):
        reports_dir = data_dir / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Two imports showing growth
        report_1 = {
            'timestamp': '2026-03-01T10:00:00Z',
            'counts': {'succeeded': 500, 'total': 500},
        }
        report_2 = {
            'timestamp': '2026-04-01T14:00:00Z',
            'counts': {'succeeded': 800, 'total': 800},
        }

        (reports_dir / 'import-csv-20260301.json').write_text(json.dumps(report_1))
        (reports_dir / 'import-csv-20260401.json').write_text(json.dumps(report_2))

        # Parse and compute growth
        imports = []
        for f in sorted(reports_dir.glob('import-csv-*.json')):
            report = json.loads(f.read_text())
            counts = report.get('counts', {})
            imports.append(counts.get('succeeded', counts.get('total', 0)))

        assert len(imports) == 2
        growth = imports[-1] - imports[0]
        assert growth == 300


class TestGracefulDegradationMissingData:
    """Verify no errors with empty/missing directories."""

    def test_empty_queries_directory(self, data_dir):
        queries_dir = data_dir / 'queries'
        queries_dir.mkdir(parents=True, exist_ok=True)

        # No JSONL files — aggregation should produce zero counts
        jsonl_files = list(queries_dir.glob('*.jsonl'))
        assert len(jsonl_files) == 0

        total = sum(
            len(f.read_text().strip().split('\n'))
            for f in jsonl_files
        )
        assert total == 0

    def test_missing_queries_directory(self, data_dir):
        queries_dir = data_dir / 'queries'
        assert not queries_dir.exists()

        # glob on non-existent dir should not error
        if queries_dir.exists():
            files = list(queries_dir.glob('*.jsonl'))
        else:
            files = []

        assert files == []

    def test_missing_reports_directory(self, data_dir):
        reports_dir = data_dir / 'reports'
        assert not reports_dir.exists()

        if reports_dir.exists():
            files = list(reports_dir.glob('import-csv-*.json'))
        else:
            files = []

        assert files == []

    def test_missing_metrics_directory(self, data_dir):
        metrics_dir = data_dir / 'metrics' / 'daily'
        assert not metrics_dir.exists()

        if metrics_dir.exists():
            files = list(metrics_dir.glob('*.jsonl'))
        else:
            files = []

        assert files == []

    def test_empty_jsonl_file(self, data_dir):
        queries_dir = data_dir / 'queries'
        queries_dir.mkdir(parents=True, exist_ok=True)

        # Create an empty JSONL file
        (queries_dir / '2026-04-07.jsonl').write_text('')

        # Reading and filtering empty lines should produce nothing
        for f in queries_dir.glob('*.jsonl'):
            content = f.read_text().strip()
            if not content:
                lines = []
            else:
                lines = content.split('\n')
            assert lines == []


class TestReportPersistence:
    """Verify setup report JSON persistence and historical comparison."""

    def test_report_saved_to_correct_path(self, data_dir):
        reports_dir = data_dir / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)

        report = {
            'generated_at': '2026-04-08T14:23:00Z',
            'health_score': 92,
            'issue_count': 1,
            'issues': [
                {
                    'severity': 'WARNING',
                    'message': '1,165 profiles missing embeddings',
                    'category': 'embeddings',
                    'action': 'linkedout embed --batch 100',
                }
            ],
            'stats': {
                'profile_count': 4012,
                'company_count': 1203,
                'connection_count': 4012,
                'embedding_count': 2847,
                'embedding_coverage_pct': 70.9,
            },
        }

        report_path = reports_dir / 'setup-report-20260408-142300.json'
        report_path.write_text(json.dumps(report, indent=2))

        assert report_path.exists()
        loaded = json.loads(report_path.read_text())
        assert loaded['health_score'] == 92
        assert loaded['stats']['profile_count'] == 4012

    def test_historical_comparison(self, data_dir):
        reports_dir = data_dir / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Previous report
        prev_report = {
            'generated_at': '2026-04-05T09:15:00Z',
            'health_score': 78,
            'issue_count': 3,
            'stats': {
                'profile_count': 3965,
                'embedding_count': 2500,
                'embedding_coverage_pct': 63.1,
            },
        }
        prev_path = reports_dir / 'setup-report-20260405-091500.json'
        prev_path.write_text(json.dumps(prev_report, indent=2))

        # Current report
        curr_report = {
            'generated_at': '2026-04-08T14:23:00Z',
            'health_score': 92,
            'issue_count': 1,
            'stats': {
                'profile_count': 4012,
                'embedding_count': 2847,
                'embedding_coverage_pct': 70.9,
            },
        }

        # Find most recent previous report
        prev_reports = sorted(reports_dir.glob('setup-report-*.json'))
        assert len(prev_reports) == 1

        prev_loaded = json.loads(prev_reports[-1].read_text())

        # Compute deltas
        profile_delta = curr_report['stats']['profile_count'] - prev_loaded['stats']['profile_count']
        coverage_delta = curr_report['stats']['embedding_coverage_pct'] - prev_loaded['stats']['embedding_coverage_pct']
        issue_delta = curr_report['issue_count'] - prev_loaded['issue_count']
        score_delta = curr_report['health_score'] - prev_loaded['health_score']

        assert profile_delta == 47
        assert coverage_delta == pytest.approx(7.8)
        assert issue_delta == -2
        assert score_delta == 14

        # Build comparison object (as the skill would)
        comparison = {
            'profile_delta': profile_delta,
            'embedding_coverage_delta': round(coverage_delta, 1),
            'issue_delta': issue_delta,
            'score_delta': score_delta,
        }

        curr_report['previous_report'] = prev_reports[-1].name
        curr_report['comparison'] = comparison

        # Save current report
        curr_path = reports_dir / 'setup-report-20260408-142300.json'
        curr_path.write_text(json.dumps(curr_report, indent=2))

        # Verify round-trip
        loaded = json.loads(curr_path.read_text())
        assert loaded['comparison']['profile_delta'] == 47
        assert loaded['previous_report'] == 'setup-report-20260405-091500.json'
