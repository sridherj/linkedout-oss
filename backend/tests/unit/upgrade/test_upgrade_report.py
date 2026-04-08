# SPDX-License-Identifier: Apache-2.0
"""Tests for upgrade report structures and persistence."""
from __future__ import annotations

import json

from linkedout.upgrade.report import (
    UpgradeReport,
    UpgradeStepResult,
    write_upgrade_report,
)


def _make_step(step: str = 'pre_flight', status: str = 'success', duration_ms: int = 100) -> UpgradeStepResult:
    return UpgradeStepResult(step=step, status=status, duration_ms=duration_ms)


def _make_report(**overrides) -> UpgradeReport:
    defaults = {
        'from_version': '0.1.0',
        'to_version': '0.2.0',
        'timestamp': '2026-04-08T14:30:12.000000Z',
        'duration_ms': 15000,
        'steps': [
            _make_step('pre_flight', 'success', 150),
            _make_step('pull_code', 'success', 8000),
            _make_step('run_migrations', 'skipped', 0),
        ],
        'whats_new': 'Added upgrade command',
        'next_steps': ['Restart the backend'],
        'failures': [],
        'rollback': 'git checkout v0.1.0',
    }
    defaults.update(overrides)
    return UpgradeReport(**defaults)


class TestUpgradeStepResult:
    """UpgradeStepResult dataclass basics."""

    def test_basic_creation(self):
        step = UpgradeStepResult(step='pre_flight', status='success', duration_ms=100)
        assert step.step == 'pre_flight'
        assert step.status == 'success'
        assert step.duration_ms == 100
        assert step.detail is None
        assert step.extra == {}

    def test_detail_and_extra(self):
        step = UpgradeStepResult(
            step='run_migrations',
            status='success',
            duration_ms=500,
            detail='Applied 3 migrations',
            extra={'migrations_applied': 3},
        )
        assert step.detail == 'Applied 3 migrations'
        assert step.extra == {'migrations_applied': 3}


class TestUpgradeReportSerialization:
    """to_dict() produces the expected JSON structure."""

    def test_contains_all_expected_keys(self):
        report = _make_report()
        d = report.to_dict()

        expected_keys = {
            'operation', 'timestamp', 'duration_ms',
            'from_version', 'to_version', 'counts', 'steps',
            'whats_new', 'next_steps', 'failures', 'rollback',
        }
        assert expected_keys == set(d.keys())

    def test_operation_is_upgrade(self):
        report = _make_report()
        assert report.to_dict()['operation'] == 'upgrade'

    def test_version_fields(self):
        report = _make_report()
        d = report.to_dict()
        assert d['from_version'] == '0.1.0'
        assert d['to_version'] == '0.2.0'

    def test_counts_computed_from_steps(self):
        report = _make_report()
        counts = report.counts
        assert counts == {'total_steps': 3, 'succeeded': 2, 'skipped': 1, 'failed': 0}

    def test_counts_with_failures(self):
        report = _make_report(steps=[
            _make_step('pre_flight', 'success', 100),
            _make_step('pull_code', 'failed', 5000),
        ])
        counts = report.counts
        assert counts == {'total_steps': 2, 'succeeded': 1, 'skipped': 0, 'failed': 1}

    def test_counts_empty_steps(self):
        report = _make_report(steps=[])
        counts = report.counts
        assert counts == {'total_steps': 0, 'succeeded': 0, 'skipped': 0, 'failed': 0}

    def test_steps_serialized_as_dicts(self):
        report = _make_report()
        d = report.to_dict()
        assert len(d['steps']) == 3
        assert d['steps'][0]['step'] == 'pre_flight'
        assert d['steps'][0]['status'] == 'success'
        assert d['steps'][0]['duration_ms'] == 150

    def test_rollback_included(self):
        report = _make_report()
        assert report.to_dict()['rollback'] == 'git checkout v0.1.0'

    def test_whats_new_none(self):
        report = _make_report(whats_new=None)
        assert report.to_dict()['whats_new'] is None

    def test_json_serializable(self):
        report = _make_report()
        serialized = json.dumps(report.to_dict())
        assert isinstance(serialized, str)
        roundtripped = json.loads(serialized)
        assert roundtripped['from_version'] == '0.1.0'


class TestUpgradeReportOverallStatus:
    """overall_status derived from step results."""

    def test_all_success(self):
        report = _make_report(steps=[_make_step(status='success')])
        assert report.overall_status == 'success'

    def test_any_failure_means_failed(self):
        report = _make_report(steps=[
            _make_step('a', 'success'),
            _make_step('b', 'failed'),
        ])
        assert report.overall_status == 'failed'

    def test_skipped_is_still_success(self):
        report = _make_report(steps=[
            _make_step('a', 'success'),
            _make_step('b', 'skipped'),
        ])
        assert report.overall_status == 'success'

    def test_empty_steps_is_success(self):
        report = _make_report(steps=[])
        assert report.overall_status == 'success'


class TestWriteUpgradeReport:
    """write_upgrade_report() persists JSON and metrics JSONL."""

    def test_writes_valid_json(self, tmp_path):
        reports_dir = tmp_path / 'reports'
        metrics_dir = tmp_path / 'metrics'
        report = _make_report()

        path = write_upgrade_report(report, reports_dir=reports_dir, metrics_dir=metrics_dir)

        data = json.loads(path.read_text())
        assert data['operation'] == 'upgrade'
        assert data['from_version'] == '0.1.0'
        assert data['to_version'] == '0.2.0'

    def test_filename_format(self, tmp_path):
        reports_dir = tmp_path / 'reports'
        metrics_dir = tmp_path / 'metrics'
        report = _make_report()

        path = write_upgrade_report(report, reports_dir=reports_dir, metrics_dir=metrics_dir)

        assert path.name == 'upgrade-20260408-143012.json'

    def test_creates_directories(self, tmp_path):
        reports_dir = tmp_path / 'deep' / 'reports'
        metrics_dir = tmp_path / 'deep' / 'metrics'
        report = _make_report()

        path = write_upgrade_report(report, reports_dir=reports_dir, metrics_dir=metrics_dir)

        assert reports_dir.is_dir()
        assert (metrics_dir / 'daily').is_dir()
        assert path.exists()

    def test_metrics_jsonl_appended(self, tmp_path):
        reports_dir = tmp_path / 'reports'
        metrics_dir = tmp_path / 'metrics'
        report = _make_report()

        write_upgrade_report(report, reports_dir=reports_dir, metrics_dir=metrics_dir)

        jsonl_path = metrics_dir / 'daily' / '2026-04-08.jsonl'
        assert jsonl_path.exists()

        line = jsonl_path.read_text().strip()
        event = json.loads(line)
        assert event['metric'] == 'upgrade'
        assert event['from'] == '0.1.0'
        assert event['to'] == '0.2.0'
        assert event['status'] == 'success'
        assert event['duration_ms'] == 15000

    def test_metrics_jsonl_valid_format(self, tmp_path):
        """Each line of the JSONL file is independently parseable JSON."""
        reports_dir = tmp_path / 'reports'
        metrics_dir = tmp_path / 'metrics'

        # Write two reports
        r1 = _make_report(from_version='0.1.0', to_version='0.2.0')
        r2 = _make_report(from_version='0.2.0', to_version='0.3.0')
        write_upgrade_report(r1, reports_dir=reports_dir, metrics_dir=metrics_dir)
        write_upgrade_report(r2, reports_dir=reports_dir, metrics_dir=metrics_dir)

        jsonl_path = metrics_dir / 'daily' / '2026-04-08.jsonl'
        lines = jsonl_path.read_text().strip().split('\n')
        assert len(lines) == 2

        for line in lines:
            event = json.loads(line)
            assert 'metric' in event
            assert 'timestamp' in event

    def test_metrics_event_has_timestamp(self, tmp_path):
        reports_dir = tmp_path / 'reports'
        metrics_dir = tmp_path / 'metrics'
        report = _make_report()

        write_upgrade_report(report, reports_dir=reports_dir, metrics_dir=metrics_dir)

        jsonl_path = metrics_dir / 'daily' / '2026-04-08.jsonl'
        event = json.loads(jsonl_path.read_text().strip())
        assert event['timestamp'] == '2026-04-08T14:30:12.000000Z'

    def test_failed_upgrade_metrics(self, tmp_path):
        reports_dir = tmp_path / 'reports'
        metrics_dir = tmp_path / 'metrics'
        report = _make_report(steps=[_make_step('pull_code', 'failed', 5000)])

        write_upgrade_report(report, reports_dir=reports_dir, metrics_dir=metrics_dir)

        jsonl_path = metrics_dir / 'daily' / '2026-04-08.jsonl'
        event = json.loads(jsonl_path.read_text().strip())
        assert event['status'] == 'failed'

    def test_report_json_has_all_fields(self, tmp_path):
        reports_dir = tmp_path / 'reports'
        metrics_dir = tmp_path / 'metrics'
        report = _make_report()

        path = write_upgrade_report(report, reports_dir=reports_dir, metrics_dir=metrics_dir)
        data = json.loads(path.read_text())

        expected_keys = {
            'operation', 'timestamp', 'duration_ms',
            'from_version', 'to_version', 'counts', 'steps',
            'whats_new', 'next_steps', 'failures', 'rollback',
        }
        assert expected_keys == set(data.keys())

    def test_uses_env_vars_when_no_dirs_given(self, tmp_path, monkeypatch):
        monkeypatch.setenv('LINKEDOUT_REPORTS_DIR', str(tmp_path / 'env_reports'))
        monkeypatch.setenv('LINKEDOUT_METRICS_DIR', str(tmp_path / 'env_metrics'))
        report = _make_report()

        path = write_upgrade_report(report)

        assert path.parent == tmp_path / 'env_reports'
        jsonl = tmp_path / 'env_metrics' / 'daily' / '2026-04-08.jsonl'
        assert jsonl.exists()


class TestUpgradeReportDefaults:
    """Default field values."""

    def test_timestamp_auto_generated(self):
        report = UpgradeReport(from_version='0.1.0', to_version='0.2.0')
        assert report.timestamp.endswith('Z')
        assert len(report.timestamp) > 20

    def test_default_lists_are_empty(self):
        r1 = UpgradeReport(from_version='0.1.0', to_version='0.2.0')
        r2 = UpgradeReport(from_version='0.1.0', to_version='0.2.0')
        r1.steps.append(_make_step())
        assert len(r2.steps) == 0

    def test_default_operation(self):
        report = UpgradeReport(from_version='0.1.0', to_version='0.2.0')
        assert report.operation == 'upgrade'
