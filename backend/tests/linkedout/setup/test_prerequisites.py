# SPDX-License-Identifier: Apache-2.0
"""Tests for prerequisites detection module."""
import subprocess
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from linkedout.setup.prerequisites import (
    DiskStatus,
    PlatformInfo,
    PostgresStatus,
    PrerequisiteReport,
    PythonStatus,
    _detect_linux_distro,
    _is_wsl,
    _parse_pg_version,
    _parse_python_version,
    check_disk_space,
    check_postgres,
    check_python,
    detect_platform,
    run_all_checks,
)


# ── Platform detection tests ─────────────────────────────────────


class TestDetectPlatform:
    def test_returns_valid_platform_info(self):
        result = detect_platform()
        assert isinstance(result, PlatformInfo)
        assert result.os in ('linux', 'macos', 'windows')
        assert result.arch in ('x86_64', 'arm64', 'i686', 'armv7l')
        assert isinstance(result.distro, str)
        assert isinstance(result.package_manager, str)

    @patch('linkedout.setup.prerequisites.platform')
    @patch('linkedout.setup.prerequisites._is_wsl', return_value=False)
    @patch('linkedout.setup.prerequisites._detect_linux_distro', return_value=('ubuntu', 'apt'))
    def test_detects_linux_ubuntu(self, mock_distro, mock_wsl, mock_platform):
        mock_platform.system.return_value = 'Linux'
        mock_platform.machine.return_value = 'x86_64'

        result = detect_platform()
        assert result.os == 'linux'
        assert result.distro == 'ubuntu'
        assert result.package_manager == 'apt'

    @patch('linkedout.setup.prerequisites.platform')
    @patch('linkedout.setup.prerequisites._is_wsl', return_value=False)
    @patch('linkedout.setup.prerequisites._detect_linux_distro', return_value=('arch', 'pacman'))
    def test_detects_linux_arch(self, mock_distro, mock_wsl, mock_platform):
        mock_platform.system.return_value = 'Linux'
        mock_platform.machine.return_value = 'x86_64'

        result = detect_platform()
        assert result.os == 'linux'
        assert result.distro == 'arch'
        assert result.package_manager == 'pacman'

    @patch('linkedout.setup.prerequisites.platform')
    @patch('linkedout.setup.prerequisites._is_wsl', return_value=False)
    @patch('linkedout.setup.prerequisites._detect_linux_distro', return_value=('fedora', 'dnf'))
    def test_detects_linux_fedora(self, mock_distro, mock_wsl, mock_platform):
        mock_platform.system.return_value = 'Linux'
        mock_platform.machine.return_value = 'x86_64'

        result = detect_platform()
        assert result.os == 'linux'
        assert result.distro == 'fedora'
        assert result.package_manager == 'dnf'

    @patch('linkedout.setup.prerequisites.platform')
    @patch('linkedout.setup.prerequisites._detect_brew', return_value='brew')
    def test_detects_macos(self, mock_brew, mock_platform):
        mock_platform.system.return_value = 'Darwin'
        mock_platform.machine.return_value = 'arm64'

        result = detect_platform()
        assert result.os == 'macos'
        assert result.distro == 'macos'
        assert result.package_manager == 'brew'
        assert result.arch == 'arm64'

    @patch('linkedout.setup.prerequisites.platform')
    @patch('linkedout.setup.prerequisites._is_wsl', return_value=True)
    @patch('linkedout.setup.prerequisites._detect_linux_distro', return_value=('ubuntu', 'apt'))
    def test_detects_wsl(self, mock_distro, mock_wsl, mock_platform):
        mock_platform.system.return_value = 'Linux'
        mock_platform.machine.return_value = 'x86_64'

        result = detect_platform()
        assert result.os == 'linux'
        assert result.distro == 'wsl'
        assert result.package_manager == 'apt'


class TestIsWSL:
    @patch('builtins.open', mock_open(read_data='Linux version 5.15.0-microsoft-standard-WSL2'))
    def test_detects_wsl_from_proc_version(self):
        assert _is_wsl() is True

    @patch('builtins.open', mock_open(read_data='Linux version 6.8.0-45-generic'))
    def test_returns_false_for_native_linux(self):
        assert _is_wsl() is False

    @patch('builtins.open', side_effect=OSError)
    def test_returns_false_on_file_error(self, mock_file):
        assert _is_wsl() is False


class TestDetectLinuxDistro:
    @patch('builtins.open', mock_open(read_data='ID=ubuntu\n'))
    def test_detects_ubuntu(self):
        distro, pkg = _detect_linux_distro()
        assert distro == 'ubuntu'
        assert pkg == 'apt'

    @patch('builtins.open', mock_open(read_data='ID=arch\n'))
    def test_detects_arch(self):
        distro, pkg = _detect_linux_distro()
        assert distro == 'arch'
        assert pkg == 'pacman'

    @patch('builtins.open', mock_open(read_data='ID=fedora\n'))
    def test_detects_fedora(self):
        distro, pkg = _detect_linux_distro()
        assert distro == 'fedora'
        assert pkg == 'dnf'

    @patch('builtins.open', side_effect=OSError)
    def test_returns_unknown_on_error(self, mock_file):
        distro, pkg = _detect_linux_distro()
        assert distro == 'unknown'
        assert pkg == 'none'


# ── PostgreSQL check tests ─────────���─────────────────────────────


class TestCheckPostgres:
    @patch('linkedout.setup.prerequisites.subprocess.run')
    def test_detects_installed_and_running(self, mock_run):
        def side_effect(cmd, **kwargs):
            if cmd[0] == 'psql':
                result = subprocess.CompletedProcess(cmd, 0, stdout='psql (PostgreSQL) 16.2\n')
                return result
            if cmd[0] == 'pg_isready':
                return subprocess.CompletedProcess(cmd, 0)
            # Extension check
            return subprocess.CompletedProcess(cmd, 0, stdout='1\n')

        mock_run.side_effect = side_effect
        result = check_postgres()

        assert result.installed is True
        assert result.running is True
        assert result.version == '16.2'
        assert result.major_version == 16
        assert result.has_pgvector is True
        assert result.has_pg_trgm is True

    @patch('linkedout.setup.prerequisites.subprocess.run', side_effect=FileNotFoundError)
    def test_not_installed(self, mock_run):
        result = check_postgres()
        assert result.installed is False
        assert result.running is False
        assert result.version is None

    @patch('linkedout.setup.prerequisites.subprocess.run')
    def test_installed_but_not_running(self, mock_run):
        def side_effect(cmd, **kwargs):
            if cmd[0] == 'psql':
                return subprocess.CompletedProcess(cmd, 0, stdout='psql (PostgreSQL) 16.2\n')
            if cmd[0] == 'pg_isready':
                return subprocess.CompletedProcess(cmd, 2)  # not accepting connections
            return subprocess.CompletedProcess(cmd, 1)

        mock_run.side_effect = side_effect
        result = check_postgres()

        assert result.installed is True
        assert result.running is False
        assert result.has_pgvector is False  # not checked if server not running

    @patch('linkedout.setup.prerequisites.subprocess.run')
    def test_missing_pgvector(self, mock_run):
        def side_effect(cmd, **kwargs):
            if cmd[0] == 'psql' and '--version' in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout='psql (PostgreSQL) 16.2\n')
            if cmd[0] == 'pg_isready':
                return subprocess.CompletedProcess(cmd, 0)
            # Extension checks
            if 'vector' in str(cmd):
                return subprocess.CompletedProcess(cmd, 0, stdout='')  # no rows
            if 'pg_trgm' in str(cmd):
                return subprocess.CompletedProcess(cmd, 0, stdout='1\n')
            return subprocess.CompletedProcess(cmd, 1)

        mock_run.side_effect = side_effect
        result = check_postgres()

        assert result.has_pgvector is False
        assert result.has_pg_trgm is True

    @patch('linkedout.setup.prerequisites.subprocess.run')
    def test_old_version(self, mock_run):
        def side_effect(cmd, **kwargs):
            if cmd[0] == 'psql':
                return subprocess.CompletedProcess(cmd, 0, stdout='psql (PostgreSQL) 12.3\n')
            return subprocess.CompletedProcess(cmd, 2)

        mock_run.side_effect = side_effect
        result = check_postgres()

        assert result.version == '12.3'
        assert result.major_version == 12


# ── Python check tests ─────���────────────────────────────────────


class TestCheckPython:
    def test_detects_current_python(self):
        result = check_python()
        assert result.installed is True
        assert result.version is not None
        # We're running tests with Python, so pip and venv should be available
        assert result.has_pip is True

    @patch('linkedout.setup.prerequisites.subprocess.run', side_effect=FileNotFoundError)
    def test_not_installed(self, mock_run):
        result = check_python()
        assert result.installed is False
        assert result.version is None
        assert result.has_pip is False
        assert result.has_venv is False

    @patch('linkedout.setup.prerequisites.subprocess.run')
    def test_old_version(self, mock_run):
        def side_effect(cmd, **kwargs):
            if cmd == ['python3', '--version']:
                return subprocess.CompletedProcess(cmd, 0, stdout='Python 3.10.5\n')
            if cmd in (['pip3', '--version'], ['pip', '--version']):
                return subprocess.CompletedProcess(cmd, 0, stdout='pip 23.0\n')
            if cmd == ['python3', '-c', 'import venv']:
                return subprocess.CompletedProcess(cmd, 0)
            return subprocess.CompletedProcess(cmd, 1)

        mock_run.side_effect = side_effect
        result = check_python()

        assert result.installed is True
        assert result.version == '3.10.5'


# ── Disk space tests ───���─────────────────────────────────────────


class TestCheckDiskSpace:
    def test_returns_valid_disk_status_for_temp_dir(self, tmp_path):
        result = check_disk_space(tmp_path)
        assert isinstance(result, DiskStatus)
        assert result.free_gb > 0
        assert result.mount_point == str(tmp_path)

    def test_walks_up_to_existing_parent(self, tmp_path):
        nonexistent = tmp_path / 'does' / 'not' / 'exist'
        result = check_disk_space(nonexistent)
        assert isinstance(result, DiskStatus)
        assert result.free_gb > 0
        # mount_point should be tmp_path since that's the highest existing parent
        assert Path(result.mount_point).exists()

    def test_default_data_dir(self):
        result = check_disk_space()
        assert isinstance(result, DiskStatus)
        assert result.free_gb > 0

    def test_sufficient_and_recommended_thresholds(self, tmp_path):
        result = check_disk_space(tmp_path)
        # Most test environments have > 5GB free
        if result.free_gb >= 5.0:
            assert result.sufficient is True
            assert result.recommended is True
        elif result.free_gb >= 2.0:
            assert result.sufficient is True
            assert result.recommended is False


# ── Version parsing tests ────────────────────────────────────────


class TestParsePgVersion:
    def test_standard_format(self):
        assert _parse_pg_version('psql (PostgreSQL) 16.2') == '16.2'

    def test_three_part_version(self):
        assert _parse_pg_version('psql (PostgreSQL) 14.10.1') == '14.10.1'

    def test_no_match(self):
        assert _parse_pg_version('no version here') is None


class TestParsePythonVersion:
    def test_standard_format(self):
        assert _parse_python_version('Python 3.12.1') == '3.12.1'

    def test_no_match(self):
        assert _parse_python_version('not python') is None


# ── Full prerequisite report tests ───────���───────────────────────


class TestRunAllChecks:
    def test_returns_prerequisite_report(self, tmp_path):
        report = run_all_checks(data_dir=tmp_path)
        assert isinstance(report, PrerequisiteReport)
        assert isinstance(report.platform, PlatformInfo)
        assert isinstance(report.postgres, PostgresStatus)
        assert isinstance(report.python, PythonStatus)
        assert isinstance(report.disk, DiskStatus)
        assert isinstance(report.blockers, list)

    @patch('linkedout.setup.prerequisites.detect_platform')
    @patch('linkedout.setup.prerequisites.check_postgres')
    @patch('linkedout.setup.prerequisites.check_python')
    @patch('linkedout.setup.prerequisites.check_disk_space')
    def test_all_pass_gives_empty_blockers(
        self, mock_disk, mock_python, mock_postgres, mock_platform
    ):
        mock_platform.return_value = PlatformInfo(
            os='linux', distro='ubuntu', package_manager='apt', arch='x86_64',
        )
        mock_postgres.return_value = PostgresStatus(
            installed=True, running=True, version='16.2', major_version=16,
            has_pgvector=True, has_pg_trgm=True,
        )
        mock_python.return_value = PythonStatus(
            installed=True, version='3.12.1', has_pip=True, has_venv=True,
        )
        mock_disk.return_value = DiskStatus(
            free_gb=50.0, mount_point='/home', sufficient=True, recommended=True,
        )

        report = run_all_checks()
        assert report.ready is True
        assert report.blockers == []

    @patch('linkedout.setup.prerequisites.detect_platform')
    @patch('linkedout.setup.prerequisites.check_postgres')
    @patch('linkedout.setup.prerequisites.check_python')
    @patch('linkedout.setup.prerequisites.check_disk_space')
    def test_missing_postgres_adds_blocker(
        self, mock_disk, mock_python, mock_postgres, mock_platform
    ):
        mock_platform.return_value = PlatformInfo(
            os='linux', distro='ubuntu', package_manager='apt', arch='x86_64',
        )
        mock_postgres.return_value = PostgresStatus(installed=False, running=False)
        mock_python.return_value = PythonStatus(
            installed=True, version='3.12.1', has_pip=True, has_venv=True,
        )
        mock_disk.return_value = DiskStatus(
            free_gb=50.0, mount_point='/home', sufficient=True, recommended=True,
        )

        report = run_all_checks()
        assert report.ready is False
        assert any('PostgreSQL is not installed' in b for b in report.blockers)

    @patch('linkedout.setup.prerequisites.detect_platform')
    @patch('linkedout.setup.prerequisites.check_postgres')
    @patch('linkedout.setup.prerequisites.check_python')
    @patch('linkedout.setup.prerequisites.check_disk_space')
    def test_old_python_adds_blocker(
        self, mock_disk, mock_python, mock_postgres, mock_platform
    ):
        mock_platform.return_value = PlatformInfo(
            os='linux', distro='ubuntu', package_manager='apt', arch='x86_64',
        )
        mock_postgres.return_value = PostgresStatus(
            installed=True, running=True, version='16.2', major_version=16,
            has_pgvector=True, has_pg_trgm=True,
        )
        mock_python.return_value = PythonStatus(
            installed=True, version='3.10.5', has_pip=True, has_venv=True,
        )
        mock_disk.return_value = DiskStatus(
            free_gb=50.0, mount_point='/home', sufficient=True, recommended=True,
        )

        report = run_all_checks()
        assert report.ready is False
        assert any('3.10.5' in b and 'too old' in b for b in report.blockers)

    @patch('linkedout.setup.prerequisites.detect_platform')
    @patch('linkedout.setup.prerequisites.check_postgres')
    @patch('linkedout.setup.prerequisites.check_python')
    @patch('linkedout.setup.prerequisites.check_disk_space')
    def test_low_disk_space_adds_blocker(
        self, mock_disk, mock_python, mock_postgres, mock_platform
    ):
        mock_platform.return_value = PlatformInfo(
            os='linux', distro='ubuntu', package_manager='apt', arch='x86_64',
        )
        mock_postgres.return_value = PostgresStatus(
            installed=True, running=True, version='16.2', major_version=16,
            has_pgvector=True, has_pg_trgm=True,
        )
        mock_python.return_value = PythonStatus(
            installed=True, version='3.12.1', has_pip=True, has_venv=True,
        )
        mock_disk.return_value = DiskStatus(
            free_gb=1.2, mount_point='/home', sufficient=False, recommended=False,
        )

        report = run_all_checks()
        assert report.ready is False
        assert any('1.2 GB' in b for b in report.blockers)

    @patch('linkedout.setup.prerequisites.detect_platform')
    @patch('linkedout.setup.prerequisites.check_postgres')
    @patch('linkedout.setup.prerequisites.check_python')
    @patch('linkedout.setup.prerequisites.check_disk_space')
    def test_windows_native_adds_blocker(
        self, mock_disk, mock_python, mock_postgres, mock_platform
    ):
        mock_platform.return_value = PlatformInfo(
            os='windows', distro='windows', package_manager='none', arch='x86_64',
        )
        mock_postgres.return_value = PostgresStatus(installed=False, running=False)
        mock_python.return_value = PythonStatus(
            installed=True, version='3.12.1', has_pip=True, has_venv=True,
        )
        mock_disk.return_value = DiskStatus(
            free_gb=50.0, mount_point='C:\\', sufficient=True, recommended=True,
        )

        report = run_all_checks()
        assert report.ready is False
        assert any('WSL2' in b for b in report.blockers)

    @patch('linkedout.setup.prerequisites.detect_platform')
    @patch('linkedout.setup.prerequisites.check_postgres')
    @patch('linkedout.setup.prerequisites.check_python')
    @patch('linkedout.setup.prerequisites.check_disk_space')
    def test_old_postgres_adds_blocker(
        self, mock_disk, mock_python, mock_postgres, mock_platform
    ):
        mock_platform.return_value = PlatformInfo(
            os='linux', distro='ubuntu', package_manager='apt', arch='x86_64',
        )
        mock_postgres.return_value = PostgresStatus(
            installed=True, running=True, version='12.3', major_version=12,
        )
        mock_python.return_value = PythonStatus(
            installed=True, version='3.12.1', has_pip=True, has_venv=True,
        )
        mock_disk.return_value = DiskStatus(
            free_gb=50.0, mount_point='/home', sufficient=True, recommended=True,
        )

        report = run_all_checks()
        assert report.ready is False
        assert any('too old' in b and '12.3' in b for b in report.blockers)
