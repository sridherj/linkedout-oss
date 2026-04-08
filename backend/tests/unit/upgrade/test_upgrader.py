# SPDX-License-Identifier: Apache-2.0
"""Tests for linkedout.upgrade.upgrader — core upgrade orchestration."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from linkedout.upgrade.report import UpgradeStepResult
from linkedout.upgrade.update_checker import UpdateInfo
from linkedout.upgrade.upgrader import UpgradeError, Upgrader


def _make_update_info(
    latest: str = '0.2.0',
    current: str = '0.1.0',
    is_outdated: bool = True,
) -> UpdateInfo:
    return UpdateInfo(
        latest_version=latest,
        current_version=current,
        release_url=f'https://github.com/sridherj/linkedout-oss/releases/tag/v{latest}',
        is_outdated=is_outdated,
        checked_at='2026-04-08T14:30:00+00:00',
    )


def _subprocess_ok(stdout: str = '', stderr: str = '') -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=stderr)


def _subprocess_fail(stdout: str = '', stderr: str = '') -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout=stdout, stderr=stderr)


@pytest.fixture()
def upgrader(tmp_path: Path) -> Upgrader:
    """Create an Upgrader with a fake repo root and mocked version."""
    git_dir = tmp_path / '.git'
    git_dir.mkdir()
    with patch('linkedout.upgrade.upgrader.__version__', '0.1.0'):
        u = Upgrader(repo_root=tmp_path)
        u._from_version = '0.1.0'
    return u


class TestDetectInstallType:
    """detect_install_type() checks for .git directory."""

    def test_git_clone(self, tmp_path: Path):
        (tmp_path / '.git').mkdir()
        with patch('linkedout.upgrade.upgrader.__version__', '0.1.0'):
            u = Upgrader(repo_root=tmp_path)
        assert u.detect_install_type() == 'git_clone'

    def test_unknown_no_git(self, tmp_path: Path):
        with patch('linkedout.upgrade.upgrader.__version__', '0.1.0'):
            u = Upgrader(repo_root=tmp_path)
        assert u.detect_install_type() == 'unknown'


class TestPreFlightCheck:
    """pre_flight_check() validates working tree and update availability."""

    def test_dirty_tree_raises(self, upgrader: Upgrader):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = _subprocess_ok(stdout='M some_file.py\n')
            with pytest.raises(UpgradeError) as exc_info:
                upgrader.pre_flight_check()

        assert 'uncommitted changes' in str(exc_info.value)
        assert exc_info.value.step_result.status == 'failed'

    def test_already_up_to_date(self, upgrader: Upgrader):
        with (
            patch('subprocess.run', return_value=_subprocess_ok(stdout='')),
            patch(
                'linkedout.upgrade.upgrader.check_for_update',
                return_value=_make_update_info(is_outdated=False, latest='0.1.0'),
            ),
        ):
            result = upgrader.pre_flight_check()

        assert result.status == 'skipped'
        assert 'latest version' in result.detail

    def test_update_available(self, upgrader: Upgrader):
        with (
            patch('subprocess.run', return_value=_subprocess_ok(stdout='')),
            patch(
                'linkedout.upgrade.upgrader.check_for_update',
                return_value=_make_update_info(latest='0.2.0', is_outdated=True),
            ),
        ):
            result = upgrader.pre_flight_check()

        assert result.status == 'success'
        assert upgrader._to_version == '0.2.0'

    def test_update_check_returns_none(self, upgrader: Upgrader):
        """Network failure returns None — treat as already up to date."""
        with (
            patch('subprocess.run', return_value=_subprocess_ok(stdout='')),
            patch('linkedout.upgrade.upgrader.check_for_update', return_value=None),
        ):
            result = upgrader.pre_flight_check()

        assert result.status == 'skipped'


class TestPullCode:
    """pull_code() runs git fetch + git pull."""

    def test_success(self, upgrader: Upgrader):
        with patch('subprocess.run', return_value=_subprocess_ok()):
            result = upgrader.pull_code()
        assert result.status == 'success'

    def test_network_error(self, upgrader: Upgrader):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = _subprocess_fail(
                stderr='fatal: Could not resolve host: github.com'
            )
            with pytest.raises(UpgradeError) as exc_info:
                upgrader.pull_code()

        assert 'could not reach the remote repository' in str(exc_info.value)

    def test_merge_conflict(self, upgrader: Upgrader):
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # fetch succeeds
                return _subprocess_ok()
            else:  # pull fails with conflict
                return _subprocess_fail(stdout='CONFLICT (content): Merge conflict in file.py')

        with patch('subprocess.run', side_effect=side_effect):
            with pytest.raises(UpgradeError) as exc_info:
                upgrader.pull_code()

        assert 'merge conflict' in str(exc_info.value)


class TestUpdateDeps:
    """update_deps() runs uv pip install."""

    def test_success(self, upgrader: Upgrader):
        with patch('subprocess.run', return_value=_subprocess_ok()):
            result = upgrader.update_deps()
        assert result.status == 'success'

    def test_failure(self, upgrader: Upgrader):
        with patch('subprocess.run', return_value=_subprocess_fail(stderr='error: no such package')):
            with pytest.raises(UpgradeError) as exc_info:
                upgrader.update_deps()
        assert 'Failed to update Python dependencies' in str(exc_info.value)


class TestRunMigrations:
    """run_migrations() runs alembic upgrade head."""

    def test_success_with_migrations(self, upgrader: Upgrader):
        with patch('subprocess.run', return_value=_subprocess_ok(
            stdout='Running upgrade abc123 -> def456\nRunning upgrade def456 -> ghi789'
        )):
            result = upgrader.run_migrations()

        assert result.status == 'success'
        assert result.extra == {'migrations_applied': 2}
        assert '2 migration(s)' in result.detail

    def test_no_pending_migrations(self, upgrader: Upgrader):
        with patch('subprocess.run', return_value=_subprocess_ok(stdout='')):
            result = upgrader.run_migrations()
        assert result.detail == 'No pending migrations'

    def test_connection_error(self, upgrader: Upgrader):
        with patch('subprocess.run', return_value=_subprocess_fail(
            stderr='could not connect to server: Connection refused'
        )):
            with pytest.raises(UpgradeError) as exc_info:
                upgrader.run_migrations()
        assert 'could not connect to PostgreSQL' in str(exc_info.value)

    def test_schema_error(self, upgrader: Upgrader):
        with patch('subprocess.run', return_value=_subprocess_fail(
            stderr='sqlalchemy.exc.OperationalError: table already exists'
        )):
            with pytest.raises(UpgradeError) as exc_info:
                upgrader.run_migrations()
        assert 'Database migration failed' in str(exc_info.value)


class TestRunVersionScripts:
    """run_version_scripts() delegates to version_migrator."""

    def test_no_scripts(self, upgrader: Upgrader):
        with patch(
            'linkedout.upgrade.upgrader.run_version_migrations', return_value=[]
        ):
            result = upgrader.run_version_scripts('0.1.0', '0.2.0')
        assert result.status == 'skipped'
        assert 'No migration scripts' in result.detail

    def test_scripts_run(self, upgrader: Upgrader):
        with patch(
            'linkedout.upgrade.upgrader.run_version_migrations',
            return_value=[
                {'script': 'v0_1_0_to_v0_2_0.py', 'status': 'success', 'duration_ms': 100, 'error': None}
            ],
        ):
            result = upgrader.run_version_scripts('0.1.0', '0.2.0')
        assert result.status == 'success'
        assert '1 version migration script' in result.detail

    def test_script_failure(self, upgrader: Upgrader):
        with patch(
            'linkedout.upgrade.upgrader.run_version_migrations',
            side_effect=RuntimeError('script error'),
        ):
            with pytest.raises(UpgradeError):
                upgrader.run_version_scripts('0.1.0', '0.2.0')


class TestPostUpgradeCheck:
    """post_upgrade_check() is non-blocking."""

    def test_health_check_passes(self, upgrader: Upgrader):
        with patch('subprocess.run', return_value=_subprocess_ok()):
            result = upgrader.post_upgrade_check()
        assert result.status == 'success'
        assert 'passed' in result.detail

    def test_health_check_fails_non_blocking(self, upgrader: Upgrader):
        with patch('subprocess.run', return_value=_subprocess_fail()):
            result = upgrader.post_upgrade_check()
        assert result.status == 'success'  # non-blocking
        assert 'issues' in result.detail

    def test_cli_not_found(self, upgrader: Upgrader):
        with patch('subprocess.run', side_effect=FileNotFoundError):
            result = upgrader.post_upgrade_check()
        assert result.status == 'skipped'


class TestRunUpgrade:
    """Full run_upgrade() orchestration."""

    def test_already_up_to_date(self, upgrader: Upgrader):
        with (
            patch('subprocess.run', return_value=_subprocess_ok(stdout='')),
            patch(
                'linkedout.upgrade.upgrader.check_for_update',
                return_value=_make_update_info(is_outdated=False),
            ),
        ):
            report = upgrader.run_upgrade()

        assert report.from_version == '0.1.0'
        assert report.to_version == '0.1.0'
        assert not report.failures

    def test_dirty_tree_stops_upgrade(self, upgrader: Upgrader):
        with patch('subprocess.run', return_value=_subprocess_ok(stdout='M dirty.py\n')):
            report = upgrader.run_upgrade()

        assert len(report.failures) == 1
        assert 'uncommitted changes' in report.failures[0]
        assert report.to_version == '0.1.0'  # unchanged

    def test_successful_upgrade(self, upgrader: Upgrader, tmp_path: Path):
        call_idx = 0

        def subprocess_side_effect(*args, **kwargs):
            nonlocal call_idx
            call_idx += 1
            cmd = args[0] if args else kwargs.get('args', [])
            if cmd and cmd[0] == 'git' and cmd[1] == 'status':
                return _subprocess_ok(stdout='')  # clean tree
            return _subprocess_ok(stdout='')

        with (
            patch('subprocess.run', side_effect=subprocess_side_effect),
            patch(
                'linkedout.upgrade.upgrader.check_for_update',
                return_value=_make_update_info(latest='0.2.0', is_outdated=True),
            ),
            patch('linkedout.upgrade.upgrader.run_version_migrations', return_value=[]),
            patch('linkedout.upgrade.upgrader.parse_changelog', return_value="What's New in v0.2.0\n---\n- Changes"),
            patch('linkedout.upgrade.upgrader.write_upgrade_report', return_value=tmp_path / 'report.json'),
            patch.object(upgrader, '_save_last_upgrade_version'),
        ):
            report = upgrader.run_upgrade()

        assert report.from_version == '0.1.0'
        assert report.to_version == '0.2.0'
        assert not report.failures
        assert report.whats_new is not None
        assert "What's New" in report.whats_new

    def test_failure_at_pull_includes_rollback(self, upgrader: Upgrader, tmp_path: Path):
        call_idx = 0

        def subprocess_side_effect(*args, **kwargs):
            nonlocal call_idx
            call_idx += 1
            cmd = args[0] if args else kwargs.get('args', [])
            if cmd and cmd[0] == 'git' and cmd[1] == 'status':
                return _subprocess_ok(stdout='')  # clean tree
            if cmd and cmd[0] == 'git' and cmd[1] == 'fetch':
                return _subprocess_fail(stderr='fatal: Could not resolve host: github.com')
            return _subprocess_ok()

        with (
            patch('subprocess.run', side_effect=subprocess_side_effect),
            patch(
                'linkedout.upgrade.upgrader.check_for_update',
                return_value=_make_update_info(latest='0.2.0', is_outdated=True),
            ),
            patch('linkedout.upgrade.upgrader.write_upgrade_report', return_value=tmp_path / 'report.json'),
        ):
            report = upgrader.run_upgrade()

        assert len(report.failures) == 1
        assert report.rollback  # rollback instructions present

    def test_failure_at_migration_includes_full_rollback(self, upgrader: Upgrader, tmp_path: Path):
        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get('args', [])
            if cmd and cmd[0] == 'alembic':
                return _subprocess_fail(stderr='could not connect to server')
            return _subprocess_ok(stdout='')

        with (
            patch('subprocess.run', side_effect=subprocess_side_effect),
            patch(
                'linkedout.upgrade.upgrader.check_for_update',
                return_value=_make_update_info(latest='0.2.0', is_outdated=True),
            ),
            patch('linkedout.upgrade.upgrader.run_version_migrations', return_value=[]),
            patch('linkedout.upgrade.upgrader.write_upgrade_report', return_value=tmp_path / 'report.json'),
        ):
            report = upgrader.run_upgrade()

        assert len(report.failures) == 1
        assert 'linkedout migrate' in report.rollback

    def test_steps_executed_in_order(self, upgrader: Upgrader, tmp_path: Path):
        executed_steps = []

        original_run = subprocess.run

        def track_subprocess(*args, **kwargs):
            cmd = args[0] if args else kwargs.get('args', [])
            if cmd:
                executed_steps.append(cmd[0] if isinstance(cmd[0], str) else str(cmd))
            return _subprocess_ok(stdout='')

        with (
            patch('subprocess.run', side_effect=track_subprocess),
            patch(
                'linkedout.upgrade.upgrader.check_for_update',
                return_value=_make_update_info(latest='0.2.0', is_outdated=True),
            ),
            patch('linkedout.upgrade.upgrader.run_version_migrations', return_value=[]),
            patch('linkedout.upgrade.upgrader.parse_changelog', return_value=''),
            patch('linkedout.upgrade.upgrader.write_upgrade_report', return_value=tmp_path / 'report.json'),
            patch.object(upgrader, '_save_last_upgrade_version'),
        ):
            report = upgrader.run_upgrade()

        # Verify steps: git status, git fetch, git pull, uv, alembic, linkedout
        assert 'git' in executed_steps  # pre-flight
        assert 'uv' in executed_steps  # deps
        assert 'alembic' in executed_steps  # migrations

    def test_report_structure_on_success(self, upgrader: Upgrader, tmp_path: Path):
        with (
            patch('subprocess.run', return_value=_subprocess_ok(stdout='')),
            patch(
                'linkedout.upgrade.upgrader.check_for_update',
                return_value=_make_update_info(latest='0.2.0', is_outdated=True),
            ),
            patch('linkedout.upgrade.upgrader.run_version_migrations', return_value=[]),
            patch('linkedout.upgrade.upgrader.parse_changelog', return_value="What's New"),
            patch('linkedout.upgrade.upgrader.write_upgrade_report', return_value=tmp_path / 'report.json'),
            patch.object(upgrader, '_save_last_upgrade_version'),
        ):
            report = upgrader.run_upgrade()

        assert report.operation == 'upgrade'
        assert report.from_version == '0.1.0'
        assert report.to_version == '0.2.0'
        assert report.duration_ms >= 0
        assert len(report.steps) > 0
        assert all(isinstance(s, UpgradeStepResult) for s in report.steps)


class TestRollbackInstructions:
    """_rollback_instructions() returns correct commands per failure point."""

    def test_pull_code_rollback(self, upgrader: Upgrader):
        result = upgrader._rollback_instructions('0.1.0', 'pull_code')
        assert 'git merge --abort' in result
        # No git checkout needed — code wasn't fully changed

    def test_update_deps_rollback(self, upgrader: Upgrader):
        result = upgrader._rollback_instructions('0.1.0', 'update_deps')
        assert 'git checkout v0.1.0' in result
        assert 'uv pip install' in result

    def test_migration_rollback(self, upgrader: Upgrader):
        result = upgrader._rollback_instructions('0.1.0', 'run_migrations')
        assert 'git checkout v0.1.0' in result
        assert 'linkedout migrate' in result

    def test_version_scripts_rollback(self, upgrader: Upgrader):
        result = upgrader._rollback_instructions('0.1.0', 'version_scripts')
        assert 'git checkout v0.1.0' in result
        assert 'linkedout migrate' in result
