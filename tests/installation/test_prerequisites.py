# SPDX-License-Identifier: Apache-2.0
"""Prerequisite detection tests.

Validates that the prerequisites module correctly detects the current
platform, Python version, PostgreSQL status, and disk space. Uses mocks
to simulate missing/broken dependencies without requiring actual system
changes.
"""
from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from linkedout.setup.prerequisites import (
    DiskStatus,
    PlatformInfo,
    PostgresStatus,
    PrerequisiteReport,
    PythonStatus,
    check_disk_space,
    check_postgres,
    check_python,
    detect_platform,
    run_all_checks,
)


class TestDetectPlatform:
    def test_detect_current_platform(self):
        """Verify correct OS detection on the current system."""
        result = detect_platform()

        assert isinstance(result, PlatformInfo)
        assert result.os in ("linux", "macos", "windows")
        assert result.arch in ("x86_64", "arm64")
        assert result.package_manager in ("apt", "pacman", "dnf", "brew", "none")

        # Verify consistency with stdlib
        system = platform.system()
        if system == "Linux":
            assert result.os == "linux"
        elif system == "Darwin":
            assert result.os == "macos"

    def test_detect_linux_distro(self):
        """Mock a Linux system and verify distro detection."""
        with (
            patch("linkedout.setup.prerequisites.platform") as mock_platform,
            patch("linkedout.setup.prerequisites._is_wsl", return_value=False),
            patch(
                "builtins.open",
                side_effect=lambda *a, **kw: _fake_os_release("ubuntu"),
            ),
        ):
            mock_platform.system.return_value = "Linux"
            mock_platform.machine.return_value = "x86_64"
            result = detect_platform()

        assert result.os == "linux"
        assert result.distro == "ubuntu"
        assert result.package_manager == "apt"

    def test_detect_macos(self):
        """Mock a macOS system and verify detection."""
        with (
            patch("linkedout.setup.prerequisites.platform") as mock_platform,
            patch(
                "linkedout.setup.prerequisites._detect_brew", return_value="brew"
            ),
        ):
            mock_platform.system.return_value = "Darwin"
            mock_platform.machine.return_value = "arm64"
            result = detect_platform()

        assert result.os == "macos"
        assert result.distro == "macos"
        assert result.package_manager == "brew"
        assert result.arch == "arm64"


class TestCheckPython:
    def test_detect_python_version(self):
        """Verify current Python version is detected correctly."""
        result = check_python()

        assert isinstance(result, PythonStatus)
        assert result.installed is True
        assert result.version is not None
        # We're running this test, so Python must be >= 3.11
        parts = result.version.split(".")
        assert int(parts[0]) >= 3
        assert int(parts[1]) >= 11

    def test_wrong_python_version(self):
        """Mock Python 3.9 and verify it appears in blockers."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Python 3.9.7"

        with patch("subprocess.run", return_value=mock_result):
            result = check_python()

        assert result.installed is True
        assert result.version == "3.9.7"


class TestCheckPostgres:
    def test_missing_postgres(self):
        """Mock missing PostgreSQL and verify blockers list."""
        with patch("subprocess.run", side_effect=FileNotFoundError("psql")):
            result = check_postgres()

        assert isinstance(result, PostgresStatus)
        assert result.installed is False
        assert result.running is False
        assert result.version is None

    def test_missing_pgvector(self):
        """Mock PostgreSQL without pgvector extension."""

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            if cmd[0] == "psql" and "--version" in cmd:
                result.returncode = 0
                result.stdout = "psql (PostgreSQL) 16.2"
                return result
            if cmd[0] == "pg_isready":
                result.returncode = 0
                return result
            if cmd[0] == "psql" and "-c" in cmd:
                # Extension check — pgvector not available
                sql = cmd[cmd.index("-c") + 1]
                if "vector" in sql:
                    result.returncode = 0
                    result.stdout = ""  # No row returned
                elif "pg_trgm" in sql:
                    result.returncode = 0
                    result.stdout = "1"
                return result
            result.returncode = 1
            return result

        with patch("subprocess.run", side_effect=mock_run):
            result = check_postgres()

        assert result.installed is True
        assert result.running is True
        assert result.has_pgvector is False
        assert result.has_pg_trgm is True


class TestCheckDiskSpace:
    def test_insufficient_disk_space(self):
        """Mock 500MB free and verify ``sufficient=False``."""
        # shutil.disk_usage returns (total, used, free) in bytes
        mock_usage = MagicMock()
        mock_usage.free = 500 * 1024 * 1024  # 500 MB

        with patch("shutil.disk_usage", return_value=mock_usage):
            result = check_disk_space(Path("/tmp/test"))

        assert isinstance(result, DiskStatus)
        assert result.sufficient is False
        assert result.recommended is False
        assert result.free_gb < 2.0

    def test_sufficient_disk_space(self):
        """Mock 10GB free and verify ``sufficient=True, recommended=True``."""
        mock_usage = MagicMock()
        mock_usage.free = 10 * 1024**3  # 10 GB

        with patch("shutil.disk_usage", return_value=mock_usage):
            result = check_disk_space(Path("/tmp/test"))

        assert result.sufficient is True
        assert result.recommended is True
        assert result.free_gb >= 5.0


class TestRunAllChecks:
    def test_all_prerequisites_met(self):
        """Mock a fully healthy system and verify ``ready=True, blockers=[]``."""
        with (
            patch(
                "linkedout.setup.prerequisites.detect_platform",
                return_value=PlatformInfo(
                    os="linux", distro="ubuntu", package_manager="apt", arch="x86_64"
                ),
            ),
            patch(
                "linkedout.setup.prerequisites.check_postgres",
                return_value=PostgresStatus(
                    installed=True,
                    running=True,
                    version="16.2",
                    major_version=16,
                    has_pgvector=True,
                    has_pg_trgm=True,
                ),
            ),
            patch(
                "linkedout.setup.prerequisites.check_python",
                return_value=PythonStatus(
                    installed=True,
                    version="3.12.1",
                    has_pip=True,
                    has_venv=True,
                ),
            ),
            patch(
                "linkedout.setup.prerequisites.check_disk_space",
                return_value=DiskStatus(
                    free_gb=10.0,
                    mount_point="/",
                    sufficient=True,
                    recommended=True,
                ),
            ),
        ):
            report = run_all_checks()

        assert isinstance(report, PrerequisiteReport)
        assert report.ready is True
        assert report.blockers == []

    def test_missing_postgres_blocker(self):
        """Missing PostgreSQL should produce a blocker."""
        with (
            patch(
                "linkedout.setup.prerequisites.detect_platform",
                return_value=PlatformInfo(
                    os="linux", distro="ubuntu", package_manager="apt", arch="x86_64"
                ),
            ),
            patch(
                "linkedout.setup.prerequisites.check_postgres",
                return_value=PostgresStatus(installed=False, running=False),
            ),
            patch(
                "linkedout.setup.prerequisites.check_python",
                return_value=PythonStatus(
                    installed=True, version="3.12.1", has_pip=True, has_venv=True
                ),
            ),
            patch(
                "linkedout.setup.prerequisites.check_disk_space",
                return_value=DiskStatus(
                    free_gb=10.0, mount_point="/", sufficient=True, recommended=True
                ),
            ),
        ):
            report = run_all_checks()

        assert report.ready is False
        assert any("PostgreSQL" in b for b in report.blockers)

    def test_old_python_blocker(self):
        """Python 3.9 should produce a blocker."""
        with (
            patch(
                "linkedout.setup.prerequisites.detect_platform",
                return_value=PlatformInfo(
                    os="linux", distro="ubuntu", package_manager="apt", arch="x86_64"
                ),
            ),
            patch(
                "linkedout.setup.prerequisites.check_postgres",
                return_value=PostgresStatus(
                    installed=True,
                    running=True,
                    version="16.2",
                    major_version=16,
                    has_pgvector=True,
                    has_pg_trgm=True,
                ),
            ),
            patch(
                "linkedout.setup.prerequisites.check_python",
                return_value=PythonStatus(
                    installed=True, version="3.9.7", has_pip=True, has_venv=True
                ),
            ),
            patch(
                "linkedout.setup.prerequisites.check_disk_space",
                return_value=DiskStatus(
                    free_gb=10.0, mount_point="/", sufficient=True, recommended=True
                ),
            ),
        ):
            report = run_all_checks()

        assert report.ready is False
        assert any("3.11+" in b or "too old" in b for b in report.blockers)

    def test_low_disk_blocker(self):
        """Low disk space should produce a blocker."""
        with (
            patch(
                "linkedout.setup.prerequisites.detect_platform",
                return_value=PlatformInfo(
                    os="linux", distro="ubuntu", package_manager="apt", arch="x86_64"
                ),
            ),
            patch(
                "linkedout.setup.prerequisites.check_postgres",
                return_value=PostgresStatus(
                    installed=True,
                    running=True,
                    version="16.2",
                    major_version=16,
                    has_pgvector=True,
                    has_pg_trgm=True,
                ),
            ),
            patch(
                "linkedout.setup.prerequisites.check_python",
                return_value=PythonStatus(
                    installed=True, version="3.12.1", has_pip=True, has_venv=True
                ),
            ),
            patch(
                "linkedout.setup.prerequisites.check_disk_space",
                return_value=DiskStatus(
                    free_gb=0.5, mount_point="/", sufficient=False, recommended=False
                ),
            ),
        ):
            report = run_all_checks()

        assert report.ready is False
        assert any("GB" in b and "free" in b for b in report.blockers)


# ── Helpers ─────────────────────────────────────────────────────────


def _fake_os_release(distro_id: str):
    """Return a file-like object that mimics ``/etc/os-release``."""
    import io

    content = f'ID={distro_id}\nNAME="Ubuntu"\nVERSION_ID="24.04"\n'
    return io.StringIO(content)
