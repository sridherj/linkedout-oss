# SPDX-License-Identifier: Apache-2.0
"""Tests for Python environment setup module."""
from unittest.mock import MagicMock, patch

import pytest

from linkedout.setup.python_env import (
    create_venv,
    install_dependencies,
    setup_python_env,
    verify_cli,
)


@pytest.fixture()
def fake_repo(tmp_path):
    """Create a minimal fake repo structure for testing."""
    backend = tmp_path / 'backend'
    backend.mkdir()
    (backend / 'requirements.txt').write_text('pydantic>=2.0\n')
    (backend / 'pyproject.toml').write_text('[project]\nname = "linkedout"\nversion = "0.1.0"\n')
    return tmp_path


class TestCreateVenv:
    @patch('linkedout.setup.python_env.subprocess.run')
    def test_creates_venv_directory(self, mock_run, fake_repo):
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        result = create_venv(fake_repo)
        assert result is True
        # Verify python3 -m venv was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == 'python3'
        assert call_args[1] == '-m'
        assert call_args[2] == 'venv'

    def test_returns_false_when_venv_already_exists(self, fake_repo):
        # Create a fake existing venv with a working python3
        venv_dir = fake_repo / '.venv' / 'bin'
        venv_dir.mkdir(parents=True)
        python_path = venv_dir / 'python3'
        python_path.write_text('#!/bin/sh\necho "Python 3.12.1"')
        python_path.chmod(0o755)

        with patch('linkedout.setup.python_env.subprocess.run') as mock_run:
            # First call checks existing python3 --version
            mock_run.return_value = MagicMock(returncode=0, stdout='Python 3.12.1', stderr='')
            result = create_venv(fake_repo)

        assert result is False

    @patch('linkedout.setup.python_env.subprocess.run')
    def test_raises_on_venv_creation_failure(self, mock_run, fake_repo):
        mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='venv failed')
        with pytest.raises(RuntimeError, match='Failed to create venv'):
            create_venv(fake_repo)


class TestInstallDependencies:
    @patch('linkedout.setup.python_env.subprocess.run')
    def test_installs_via_uv_pipeline(self, mock_run, fake_repo):
        # All subprocess calls succeed
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')

        report = install_dependencies(fake_repo)

        assert report.counts.failed == 0
        assert report.counts.succeeded == 2  # requirements, editable
        assert mock_run.call_count == 2

    @patch('linkedout.setup.python_env.shutil.which', return_value=None)
    @patch('linkedout.setup.python_env.subprocess.run')
    def test_falls_back_to_pip_when_uv_fails(self, mock_run, mock_which, fake_repo):
        # shutil.which('uv') returns None → falls back to _install_via_pip()
        # _install_via_pip makes 2 subprocess calls (requirements + editable)
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')

        report = install_dependencies(fake_repo)
        # Should succeed via pip fallback (2 pip calls)
        assert report.counts.succeeded == 2
        assert report.counts.failed == 0
        assert mock_run.call_count == 2

    @patch('linkedout.setup.python_env.subprocess.run')
    def test_reports_failure_on_requirements_install_error(self, mock_run, fake_repo):
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # uv install succeeds
                return MagicMock(returncode=0, stdout='', stderr='')
            # requirements install fails
            return MagicMock(returncode=1, stdout='', stderr='install failed')

        mock_run.side_effect = side_effect

        report = install_dependencies(fake_repo)
        assert report.counts.failed == 1


class TestVerifyCli:
    @patch('linkedout.setup.python_env.subprocess.run')
    def test_returns_true_when_command_exists(self, mock_run, fake_repo):
        # Create fake linkedout binary
        venv_bin = fake_repo / '.venv' / 'bin'
        venv_bin.mkdir(parents=True, exist_ok=True)
        linkedout_cmd = venv_bin / 'linkedout'
        linkedout_cmd.write_text('#!/bin/sh\necho "linkedout v0.1.0"')
        linkedout_cmd.chmod(0o755)

        mock_run.return_value = MagicMock(returncode=0, stdout='linkedout v0.1.0', stderr='')

        assert verify_cli(fake_repo) is True

    def test_returns_false_when_command_missing(self, fake_repo):
        # No .venv/bin/linkedout exists
        assert verify_cli(fake_repo) is False

    @patch('linkedout.setup.python_env.subprocess.run')
    def test_returns_false_on_nonzero_exit(self, mock_run, fake_repo):
        venv_bin = fake_repo / '.venv' / 'bin'
        venv_bin.mkdir(parents=True, exist_ok=True)
        linkedout_cmd = venv_bin / 'linkedout'
        linkedout_cmd.write_text('#!/bin/sh\nexit 1')
        linkedout_cmd.chmod(0o755)

        mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='error')

        assert verify_cli(fake_repo) is False


class TestSetupPythonEnv:
    @patch('linkedout.setup.python_env.verify_cli', return_value=True)
    @patch('linkedout.setup.python_env.install_dependencies')
    @patch('linkedout.setup.python_env.create_venv', return_value=True)
    def test_full_setup_succeeds(self, mock_venv, mock_install, mock_cli, fake_repo):
        from shared.utilities.operation_report import OperationCounts, OperationReport

        mock_install.return_value = OperationReport(
            operation='python-env-install',
            counts=OperationCounts(total=3, succeeded=3),
        )

        report = setup_python_env(fake_repo)

        assert report.counts.failed == 0
        assert report.counts.succeeded == 3
        mock_venv.assert_called_once_with(fake_repo)
        mock_install.assert_called_once_with(fake_repo)
        mock_cli.assert_called_once_with(fake_repo)

    @patch('linkedout.setup.python_env.create_venv', side_effect=RuntimeError('venv failed'))
    def test_returns_early_on_venv_failure(self, mock_venv, fake_repo):
        report = setup_python_env(fake_repo)

        assert report.counts.failed >= 1
        assert 'Create venv manually' in report.next_steps[0]
