# SPDX-License-Identifier: Apache-2.0
"""OS detection and dependency verification for LinkedOut setup.

This is the first step in the setup flow. All checks are read-only and
non-destructive — no subprocess calls modify system state.

Detects:
- Platform (OS, distro, package manager, architecture)
- PostgreSQL (installed, running, version, pgvector, pg_trgm)
- Python (version, pip, venv)
- Disk space (free GB, sufficient/recommended thresholds)
"""
from __future__ import annotations

import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_SUBPROCESS_TIMEOUT = 10  # seconds — max for any version check


@dataclass
class PlatformInfo:
    """Detected operating system and package manager."""

    os: str  # "linux", "macos", "windows"
    distro: str  # "ubuntu", "arch", "fedora", "macos", "wsl"
    package_manager: str  # "apt", "pacman", "dnf", "brew", "none"
    arch: str  # "x86_64", "arm64"


@dataclass
class PostgresStatus:
    """PostgreSQL installation and runtime status."""

    installed: bool
    running: bool
    version: str | None = None  # e.g., "16.2"
    major_version: int | None = None  # e.g., 16
    has_pgvector: bool = False
    has_pg_trgm: bool = False


@dataclass
class PythonStatus:
    """Python installation status."""

    installed: bool
    version: str | None = None  # e.g., "3.12.1"
    has_pip: bool = False
    has_venv: bool = False


@dataclass
class DiskStatus:
    """Disk space check for the data directory."""

    free_gb: float
    mount_point: str
    sufficient: bool = False  # >= 2 GB
    recommended: bool = False  # >= 5 GB


@dataclass
class PrerequisiteReport:
    """Aggregated result of all prerequisite checks."""

    platform: PlatformInfo
    postgres: PostgresStatus
    python: PythonStatus
    disk: DiskStatus
    ready: bool = False  # all checks pass
    blockers: list[str] = field(default_factory=list)


def detect_platform() -> PlatformInfo:
    """Detect the current operating system, distribution, and package manager.

    Returns:
        PlatformInfo with OS, distro, package manager, and architecture.
    """
    system = platform.system()
    arch = platform.machine()
    # Normalize arch names
    if arch in ('AMD64', 'x86_64'):
        arch = 'x86_64'
    elif arch in ('aarch64', 'arm64'):
        arch = 'arm64'

    if system == 'Darwin':
        return PlatformInfo(os='macos', distro='macos', package_manager=_detect_brew(), arch=arch)

    if system == 'Linux':
        # Check for WSL first
        if _is_wsl():
            distro, pkg_mgr = _detect_linux_distro()
            return PlatformInfo(os='linux', distro='wsl', package_manager=pkg_mgr, arch=arch)
        distro, pkg_mgr = _detect_linux_distro()
        return PlatformInfo(os='linux', distro=distro, package_manager=pkg_mgr, arch=arch)

    if system == 'Windows':
        return PlatformInfo(os='windows', distro='windows', package_manager='none', arch=arch)

    return PlatformInfo(os=system.lower(), distro='unknown', package_manager='none', arch=arch)


def check_postgres() -> PostgresStatus:
    """Check PostgreSQL installation and runtime status.

    Checks:
    - ``psql --version`` for client version
    - ``pg_isready`` for running server
    - Version >= 14 (pgvector compatibility)
    - pgvector and pg_trgm extension availability (if server running)

    Returns:
        PostgresStatus with installation and extension details.
    """
    # Check psql version
    version = None
    major_version = None
    installed = False

    try:
        result = subprocess.run(
            ['psql', '--version'],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        if result.returncode == 0:
            installed = True
            version = _parse_pg_version(result.stdout)
            if version:
                try:
                    major_version = int(version.split('.')[0])
                except (ValueError, IndexError):
                    pass
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Check if server is running
    running = False
    try:
        result = subprocess.run(
            ['pg_isready'],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        running = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Check extensions (only if server is running)
    has_pgvector = False
    has_pg_trgm = False
    if running:
        has_pgvector = _check_pg_extension('vector')
        has_pg_trgm = _check_pg_extension('pg_trgm')

    return PostgresStatus(
        installed=installed,
        running=running,
        version=version,
        major_version=major_version,
        has_pgvector=has_pgvector,
        has_pg_trgm=has_pg_trgm,
    )


def check_python() -> PythonStatus:
    """Check Python installation and capabilities.

    Checks:
    - ``python3 --version`` >= 3.11
    - pip/pip3 available
    - venv module importable

    Returns:
        PythonStatus with version and capability details.
    """
    version = None
    installed = False

    try:
        result = subprocess.run(
            ['python3', '--version'],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        if result.returncode == 0:
            installed = True
            version = _parse_python_version(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Check pip
    has_pip = False
    for cmd in (['pip3', '--version'], ['pip', '--version']):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT,
            )
            if result.returncode == 0:
                has_pip = True
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # Check venv
    has_venv = False
    try:
        result = subprocess.run(
            ['python3', '-c', 'import venv'],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        has_venv = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return PythonStatus(
        installed=installed,
        version=version,
        has_pip=has_pip,
        has_venv=has_venv,
    )


def check_disk_space(data_dir: Path | None = None) -> DiskStatus:
    """Check free disk space on the data directory mount point.

    Args:
        data_dir: Path to check. Defaults to ``~/linkedout-data/``.
            If the directory doesn't exist yet, walks up to the
            nearest existing parent.

    Returns:
        DiskStatus with free space and threshold flags.
    """
    if data_dir is None:
        data_dir = Path.home() / 'linkedout-data'

    # Walk up to existing parent if path doesn't exist
    check_path = Path(data_dir)
    while not check_path.exists() and check_path.parent != check_path:
        check_path = check_path.parent

    try:
        usage = shutil.disk_usage(str(check_path))
        free_gb = usage.free / (1024 ** 3)
    except OSError:
        free_gb = 0.0

    return DiskStatus(
        free_gb=round(free_gb, 1),
        mount_point=str(check_path),
        sufficient=free_gb >= 2.0,
        recommended=free_gb >= 5.0,
    )


def run_all_checks(data_dir: Path | None = None) -> PrerequisiteReport:
    """Run all prerequisite checks and return an aggregated report.

    Args:
        data_dir: Override for the data directory path. Defaults to
            ``~/linkedout-data/``.

    Returns:
        PrerequisiteReport with all check results and blockers list.
    """
    plat = detect_platform()
    pg = check_postgres()
    py = check_python()
    disk = check_disk_space(data_dir)

    blockers: list[str] = []

    # Platform blockers
    if plat.os == 'windows' and plat.distro != 'wsl':
        blockers.append(
            'Windows native is not supported. Install WSL2: '
            'https://learn.microsoft.com/en-us/windows/wsl/install'
        )

    # PostgreSQL blockers
    if not pg.installed:
        blockers.append('PostgreSQL is not installed. Run the system setup script.')
    elif not pg.running:
        blockers.append('PostgreSQL is installed but not running. Start the service.')
    elif pg.major_version is not None and pg.major_version < 14:
        blockers.append(
            f'PostgreSQL {pg.version} is too old. Version 14+ is required for pgvector.'
        )

    # Python blockers
    if not py.installed:
        blockers.append('Python 3.11+ is required but not found.')
    elif py.version:
        parts = py.version.split('.')
        try:
            major, minor = int(parts[0]), int(parts[1])
            if major < 3 or (major == 3 and minor < 11):
                blockers.append(
                    f'Python {py.version} is too old. Version 3.11+ is required.'
                )
        except (ValueError, IndexError):
            pass

    if not py.has_pip:
        blockers.append('pip is not available. Install python3-pip.')

    if not py.has_venv:
        blockers.append('Python venv module is not available. Install python3-venv.')

    # Disk blockers
    if not disk.sufficient:
        blockers.append(
            f'Only {disk.free_gb:.1f} GB free on {disk.mount_point}. '
            f'Minimum 2 GB required.'
        )

    ready = len(blockers) == 0

    return PrerequisiteReport(
        platform=plat,
        postgres=pg,
        python=py,
        disk=disk,
        ready=ready,
        blockers=blockers,
    )


# ── Internal helpers ──────────────────────────────────────────────


def _is_wsl() -> bool:
    """Detect Windows Subsystem for Linux via /proc/version."""
    try:
        with open('/proc/version', encoding='utf-8') as f:
            content = f.read().lower()
            return 'microsoft' in content or 'wsl' in content
    except OSError:
        return False


def _detect_linux_distro() -> tuple[str, str]:
    """Detect Linux distribution and package manager from /etc/os-release.

    Returns:
        Tuple of (distro_name, package_manager).
    """
    distro_id = ''
    try:
        with open('/etc/os-release', encoding='utf-8') as f:
            for line in f:
                if line.startswith('ID='):
                    distro_id = line.split('=', 1)[1].strip().strip('"').lower()
                    break
                if line.startswith('ID_LIKE='):
                    distro_id = line.split('=', 1)[1].strip().strip('"').lower()
    except OSError:
        pass

    # Map distro to package manager
    if distro_id in ('ubuntu', 'debian', 'linuxmint', 'pop'):
        return distro_id, 'apt'
    if 'ubuntu' in distro_id or 'debian' in distro_id:
        return distro_id, 'apt'
    if distro_id in ('arch', 'manjaro', 'endeavouros'):
        return distro_id, 'pacman'
    if 'arch' in distro_id:
        return distro_id, 'pacman'
    if distro_id in ('fedora', 'rhel', 'centos', 'rocky', 'alma'):
        return distro_id, 'dnf'
    if 'fedora' in distro_id or 'rhel' in distro_id:
        return distro_id, 'dnf'

    return distro_id or 'unknown', 'none'


def _detect_brew() -> str:
    """Check if Homebrew is available on macOS."""
    try:
        result = subprocess.run(
            ['brew', '--version'],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        return 'brew' if result.returncode == 0 else 'none'
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 'none'


def _parse_pg_version(version_output: str) -> str | None:
    """Extract version number from ``psql --version`` output.

    Example input: ``psql (PostgreSQL) 16.2``
    """
    match = re.search(r'(\d+\.\d+(?:\.\d+)?)', version_output)
    return match.group(1) if match else None


def _parse_python_version(version_output: str) -> str | None:
    """Extract version from ``python3 --version`` output.

    Example input: ``Python 3.12.1``
    """
    match = re.search(r'(\d+\.\d+\.\d+)', version_output)
    return match.group(1) if match else None


def _check_pg_extension(extension_name: str) -> bool:
    """Check if a PostgreSQL extension is available.

    Runs a query against pg_available_extensions. Returns False on any
    error (connection refused, extension not found, etc.).
    """
    try:
        result = subprocess.run(
            [
                'psql',
                '-t',  # tuples only
                '-A',  # unaligned
                '-c',
                f"SELECT 1 FROM pg_available_extensions WHERE name = '{extension_name}'",
            ],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        return result.returncode == 0 and '1' in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
