# SPDX-License-Identifier: Apache-2.0
"""Tests for the OperationReport framework."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.utilities.operation_report import (
    CoverageGap,
    OperationCounts,
    OperationFailure,
    OperationReport,
    _get_reports_dir,
)


def _make_full_report() -> OperationReport:
    """Build a fully-populated report for reuse across tests."""
    return OperationReport(
        operation='import-csv',
        timestamp='2026-04-07T14:23:05.000000Z',
        duration_ms=1234.5,
        counts=OperationCounts(total=3870, succeeded=3847, skipped=23, failed=0),
        coverage_gaps=[
            CoverageGap(type='missing_company', count=156, detail='Missing companies: 156'),
        ],
        failures=[
            OperationFailure(item='John Doe', reason='duplicate LinkedIn URL'),
        ],
        next_steps=[
            'Run `linkedout compute-affinity` to calculate affinity scores',
        ],
    )


class TestGetReportsDir:
    """Tests for _get_reports_dir() directory resolution."""

    def test_env_override(self, tmp_path, monkeypatch):
        """LINKEDOUT_REPORTS_DIR env var overrides the default path."""
        monkeypatch.setenv('LINKEDOUT_REPORTS_DIR', str(tmp_path / 'custom'))
        assert _get_reports_dir() == tmp_path / 'custom'

    def test_default_when_env_unset(self, monkeypatch):
        """Falls back to ~/linkedout-data/reports/ when env is unset."""
        monkeypatch.delenv('LINKEDOUT_REPORTS_DIR', raising=False)
        expected = Path.home() / 'linkedout-data' / 'reports'
        assert _get_reports_dir() == expected


class TestOperationReportToDict:
    """Tests for to_dict() serialization."""

    def test_contains_all_expected_keys(self):
        """to_dict() returns a dict with all public fields."""
        report = _make_full_report()
        d = report.to_dict()

        assert d['operation'] == 'import-csv'
        assert d['timestamp'] == '2026-04-07T14:23:05.000000Z'
        assert d['duration_ms'] == 1234.5
        assert d['counts'] == {'total': 3870, 'succeeded': 3847, 'skipped': 23, 'failed': 0}
        assert len(d['coverage_gaps']) == 1
        assert d['coverage_gaps'][0]['type'] == 'missing_company'
        assert len(d['failures']) == 1
        assert d['failures'][0]['item'] == 'John Doe'
        assert d['next_steps'] == [
            'Run `linkedout compute-affinity` to calculate affinity scores',
        ]

    def test_excludes_saved_path(self):
        """to_dict() does not include the internal _saved_path field."""
        report = _make_full_report()
        d = report.to_dict()
        assert '_saved_path' not in d

    def test_empty_report_serializes(self):
        """An all-defaults report still produces a valid dict."""
        report = OperationReport(operation='test-op')
        d = report.to_dict()

        assert d['operation'] == 'test-op'
        assert d['counts'] == {'total': 0, 'succeeded': 0, 'skipped': 0, 'failed': 0}
        assert d['coverage_gaps'] == []
        assert d['failures'] == []
        assert d['next_steps'] == []


class TestOperationReportSave:
    """Tests for save() — JSON persistence."""

    def test_writes_valid_json(self, tmp_path):
        """save() writes a valid JSON file with indent=2."""
        report = _make_full_report()
        path = report.save(reports_dir=tmp_path)

        content = path.read_text()
        data = json.loads(content)
        assert data['operation'] == 'import-csv'
        # Verify indent=2 formatting (not compact)
        assert '\n' in content
        assert '  ' in content

    def test_filename_format(self, tmp_path):
        """Filename is {operation}-YYYYMMDD-HHMMSS.json derived from timestamp."""
        report = _make_full_report()
        path = report.save(reports_dir=tmp_path)

        assert path.name == 'import-csv-20260407-142305.json'

    def test_creates_directory_if_missing(self, tmp_path):
        """save() creates the reports directory if it doesn't exist."""
        nested = tmp_path / 'deep' / 'reports'
        assert not nested.exists()

        report = _make_full_report()
        path = report.save(reports_dir=nested)

        assert nested.is_dir()
        assert path.exists()

    def test_returns_path(self, tmp_path):
        """save() returns the Path where the report was written."""
        report = _make_full_report()
        path = report.save(reports_dir=tmp_path)

        assert isinstance(path, Path)
        assert path.parent == tmp_path
        assert path.exists()

    def test_json_contains_all_fields(self, tmp_path):
        """The saved JSON includes all expected top-level keys."""
        report = _make_full_report()
        path = report.save(reports_dir=tmp_path)
        data = json.loads(path.read_text())

        expected_keys = {
            'operation', 'timestamp', 'duration_ms',
            'counts', 'coverage_gaps', 'failures', 'next_steps',
        }
        assert expected_keys == set(data.keys())

    def test_uses_env_var_when_no_dir_given(self, tmp_path, monkeypatch):
        """save() uses LINKEDOUT_REPORTS_DIR when reports_dir is None."""
        monkeypatch.setenv('LINKEDOUT_REPORTS_DIR', str(tmp_path))
        report = _make_full_report()
        path = report.save()

        assert path.parent == tmp_path

    def test_sets_saved_path(self, tmp_path):
        """save() stores the path internally for print_summary() to reference."""
        report = _make_full_report()
        assert report._saved_path is None

        path = report.save(reports_dir=tmp_path)
        assert report._saved_path == path


class TestOperationReportPrintSummary:
    """Tests for print_summary() — human-readable output."""

    def test_full_output_format(self, tmp_path, capsys):
        """print_summary() after save() prints all sections."""
        report = _make_full_report()
        report.save(reports_dir=tmp_path)
        report.print_summary()

        output = capsys.readouterr().out
        assert 'Results:' in output
        assert 'Succeeded: 3,847' in output
        assert 'Skipped:   23' in output
        assert 'Failed:    0' in output
        assert 'Coverage:' in output
        assert 'Missing companies: 156' in output
        assert 'Next steps:' in output
        assert 'linkedout compute-affinity' in output
        assert 'Report saved:' in output

    def test_omits_coverage_when_no_gaps(self, capsys):
        """Coverage section is omitted when coverage_gaps is empty."""
        report = OperationReport(
            operation='test-op',
            counts=OperationCounts(total=10, succeeded=10),
        )
        report.print_summary()

        output = capsys.readouterr().out
        assert 'Results:' in output
        assert 'Coverage:' not in output

    def test_omits_next_steps_when_empty(self, capsys):
        """Next steps section is omitted when next_steps is empty."""
        report = OperationReport(
            operation='test-op',
            counts=OperationCounts(total=10, succeeded=10),
        )
        report.print_summary()

        output = capsys.readouterr().out
        assert 'Next steps:' not in output

    def test_omits_report_path_before_save(self, capsys):
        """Report saved line is omitted when save() hasn't been called."""
        report = OperationReport(operation='test-op')
        report.print_summary()

        output = capsys.readouterr().out
        assert 'Report saved:' not in output

    def test_numbers_formatted_with_commas(self, capsys):
        """Large numbers use comma separators for readability."""
        report = OperationReport(
            operation='import-csv',
            counts=OperationCounts(total=1000000, succeeded=999999, skipped=1, failed=0),
        )
        report.print_summary()

        output = capsys.readouterr().out
        assert '999,999' in output
        assert '1,000,000' not in output  # succeeded is shown, not total

    def test_empty_report_produces_sensible_output(self, capsys):
        """An all-zeros report still prints a sensible Results section."""
        report = OperationReport(operation='noop')
        report.print_summary()

        output = capsys.readouterr().out
        assert 'Results:' in output
        assert 'Succeeded: 0' in output
        assert 'Skipped:   0' in output
        assert 'Failed:    0' in output
        # No coverage or next steps sections
        assert 'Coverage:' not in output
        assert 'Next steps:' not in output

    def test_multiple_coverage_gaps(self, capsys):
        """Multiple coverage gaps are each printed on their own line."""
        report = OperationReport(
            operation='import-csv',
            coverage_gaps=[
                CoverageGap(type='missing_company', count=156, detail='Missing companies: 156'),
                CoverageGap(type='missing_embedding', count=42, detail='Missing embeddings: 42'),
            ],
        )
        report.print_summary()

        output = capsys.readouterr().out
        assert 'Missing companies: 156' in output
        assert 'Missing embeddings: 42' in output

    def test_multiple_next_steps(self, capsys):
        """Multiple next steps are each printed with arrow prefix."""
        report = OperationReport(
            operation='import-csv',
            next_steps=[
                'Run `linkedout compute-affinity` to calculate scores',
                'Run `linkedout embed` to generate embeddings',
            ],
        )
        report.print_summary()

        output = capsys.readouterr().out
        assert '\u2192 Run `linkedout compute-affinity`' in output
        assert '\u2192 Run `linkedout embed`' in output

    def test_report_path_uses_tilde(self, tmp_path, capsys, monkeypatch):
        """Report path uses ~ shorthand when under the user's home directory."""
        # Create a fake home subdirectory
        fake_home = tmp_path / 'fakehome'
        fake_home.mkdir()
        monkeypatch.setattr(Path, 'home', lambda: fake_home)

        reports_dir = fake_home / 'linkedout-data' / 'reports'
        report = _make_full_report()
        report.save(reports_dir=reports_dir)
        report.print_summary()

        output = capsys.readouterr().out
        assert 'Report saved: ~/linkedout-data/reports/' in output


class TestOperationReportDefaults:
    """Tests for default field values."""

    def test_timestamp_auto_generated(self):
        """Timestamp is auto-generated when not provided."""
        report = OperationReport(operation='test')
        assert report.timestamp.endswith('Z')
        assert len(report.timestamp) > 20  # ISO 8601 format

    def test_default_counts_are_zero(self):
        """Default OperationCounts has all zeros."""
        report = OperationReport(operation='test')
        assert report.counts.total == 0
        assert report.counts.succeeded == 0
        assert report.counts.skipped == 0
        assert report.counts.failed == 0

    def test_default_lists_are_empty(self):
        """Default lists are empty (not shared across instances)."""
        r1 = OperationReport(operation='a')
        r2 = OperationReport(operation='b')

        r1.coverage_gaps.append(CoverageGap(type='x', count=1, detail='x'))
        assert len(r2.coverage_gaps) == 0  # Independent instances
