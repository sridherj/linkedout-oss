# SPDX-License-Identifier: Apache-2.0
"""Core upgrade orchestration — detect, pull, migrate, report.

The ``Upgrader`` class drives the full ``linkedout upgrade`` flow:
pre-flight checks, git pull, dependency update, Alembic migrations,
version migration scripts, post-upgrade health check, and "What's New".

All user-facing text follows the UX design doc
(``docs/designs/upgrade-flow-ux.md``).
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from linkedout.upgrade.changelog_parser import parse_changelog
from linkedout.upgrade.extension_updater import (
    check_extension_installed,
    download_extension_zip,
    fetch_expected_checksum,
    get_sideload_instructions,
    verify_checksum,
)
from linkedout.upgrade.logging import get_upgrade_logger, log_step
from linkedout.upgrade.report import UpgradeReport, UpgradeStepResult, write_upgrade_report
from linkedout.upgrade.update_checker import check_for_update
from linkedout.upgrade.version_migrator import run_version_migrations
from linkedout.version import __version__, _repo_root


_STATE_DIR = Path.home() / 'linkedout-data' / 'state'
_LAST_UPGRADE_FILE = _STATE_DIR / '.last-upgrade-version'


class UpgradeError(Exception):
    """Raised when the upgrade must stop at a particular step."""

    def __init__(self, message: str, step_result: UpgradeStepResult):
        super().__init__(message)
        self.step_result = step_result


class Upgrader:
    """Orchestrates the full upgrade lifecycle.

    Args:
        repo_root: Path to the repository root. Defaults to auto-detection.
        verbose: If True, show detailed command output.
    """

    def __init__(
        self,
        *,
        repo_root: Path | None = None,
        verbose: bool = False,
    ):
        self.repo_root = repo_root or _repo_root()
        self.verbose = verbose
        self.logger = get_upgrade_logger()
        self._from_version: str = __version__
        self._to_version: str | None = None

    def detect_install_type(self) -> str:
        """Detect the installation type. Only ``git_clone`` is supported in v1."""
        git_dir = self.repo_root / '.git'
        if git_dir.exists():
            self.logger.info('Detected install type: git_clone')
            return 'git_clone'
        self.logger.warning('No .git directory found — cannot determine install type')
        return 'unknown'

    def pre_flight_check(self) -> UpgradeStepResult:
        """Verify the working tree is clean and an update is available.

        Returns an ``UpgradeStepResult``. On failure, raises ``UpgradeError``.
        """
        with log_step(self.logger, 'pre_flight') as ctx:
            # Check for dirty working tree
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True,
                text=True,
                cwd=self.repo_root,
            )
            if result.stdout.strip():
                msg = (
                    'Cannot upgrade — you have uncommitted changes in your '
                    'LinkedOut directory.\n\n'
                    '  Commit or stash your changes first, then re-run /linkedout-upgrade.\n\n'
                    '  To see what\'s changed:\n'
                    f'    cd {self.repo_root} && git status'
                )
                ctx.status = 'failed'
                ctx.detail = msg
            elif (update_info := check_for_update()) is None or not update_info.is_outdated:
                ctx.status = 'skipped'
                ctx.detail = f'Already running the latest version (v{self._from_version}).'
            else:
                self._to_version = update_info.latest_version
                ctx.detail = f'Update available: v{self._from_version} -> v{self._to_version}'

        assert ctx.result is not None
        if ctx.result.status == 'failed':
            raise UpgradeError(ctx.result.detail or 'Pre-flight check failed', ctx.result)
        return ctx.result

    def pull_code(self) -> UpgradeStepResult:
        """Pull latest code from the remote repository."""
        with log_step(self.logger, 'pull_code') as ctx:
            # Fetch
            fetch_result = subprocess.run(
                ['git', 'fetch', 'origin'],
                capture_output=True,
                text=True,
                cwd=self.repo_root,
            )
            if fetch_result.returncode != 0:
                stderr = fetch_result.stderr.strip()
                if 'Could not resolve' in stderr or 'unable to access' in stderr:
                    msg = (
                        'Git pull failed — could not reach the remote repository.\n\n'
                        '  Check your internet connection and try again.\n\n'
                        '  If you\'re behind a proxy or firewall:\n'
                        f'    cd {self.repo_root}\n'
                        '    git remote -v                 # verify the remote URL\n'
                        '    git fetch origin              # test connectivity\n\n'
                        '  Your LinkedOut installation is unchanged — no rollback needed.'
                    )
                else:
                    msg = f'Git fetch failed: {stderr}'
                ctx.status = 'failed'
                ctx.detail = msg
            else:
                # Pull
                pull_result = subprocess.run(
                    ['git', 'pull', 'origin', 'main'],
                    capture_output=True,
                    text=True,
                    cwd=self.repo_root,
                )
                if pull_result.returncode != 0:
                    stderr = pull_result.stderr.strip()
                    stdout = pull_result.stdout.strip()
                    combined = f'{stdout}\n{stderr}'.strip()
                    if 'CONFLICT' in combined or 'merge conflict' in combined.lower():
                        msg = (
                            'Git pull failed — merge conflict detected.\n\n'
                            '  You have local changes that conflict with the upstream '
                            'update.\n'
                            '  This typically happens if you\'ve modified LinkedOut source '
                            'files directly.\n\n'
                            '  To resolve:\n'
                            f'    cd {self.repo_root}\n'
                            '    git status                    # see which files conflict\n'
                            '    git merge --abort             # abort the merge\n'
                            '    git stash                     # stash your local changes\n'
                            '    linkedout upgrade             # re-run the upgrade\n'
                            '    git stash pop                 # re-apply your changes\n\n'
                            '  If you don\'t need your local changes:\n'
                            f'    cd {self.repo_root}\n'
                            '    git merge --abort\n'
                            '    git checkout -- .\n'
                            '    linkedout upgrade'
                        )
                    else:
                        msg = f'Git pull failed: {combined}'
                    ctx.status = 'failed'
                    ctx.detail = msg
                else:
                    ctx.detail = 'Code updated successfully'

        assert ctx.result is not None
        if ctx.result.status == 'failed':
            raise UpgradeError(ctx.result.detail or 'Pull failed', ctx.result)
        return ctx.result

    def update_deps(self) -> UpgradeStepResult:
        """Update Python dependencies via ``uv pip install``."""
        with log_step(self.logger, 'update_deps') as ctx:
            result = subprocess.run(
                ['uv', 'pip', 'install', '-e', '.[dev]'],
                capture_output=True,
                text=True,
                cwd=self.repo_root / 'backend',
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                error_lines = stderr.split('\n')
                if len(error_lines) > 5:
                    stderr = '\n'.join(error_lines[:5]) + '\n  ...'
                msg = (
                    'Failed to update Python dependencies.\n\n'
                    f'  uv pip install returned an error:\n    {stderr}\n\n'
                    '  To retry:\n'
                    f'    cd {self.repo_root}\n'
                    '    uv pip install -e "./backend[dev]"'
                )
                ctx.status = 'failed'
                ctx.detail = msg
            else:
                ctx.detail = 'Dependencies updated'

        assert ctx.result is not None
        if ctx.result.status == 'failed':
            raise UpgradeError(ctx.result.detail or 'Dependency update failed', ctx.result)
        return ctx.result

    def run_migrations(self) -> UpgradeStepResult:
        """Run Alembic database migrations."""
        with log_step(self.logger, 'run_migrations') as ctx:
            result = subprocess.run(
                ['alembic', 'upgrade', 'head'],
                capture_output=True,
                text=True,
                cwd=self.repo_root / 'backend',
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                error_lines = stderr.split('\n')
                if len(error_lines) > 5:
                    stderr = '\n'.join(error_lines[:5]) + '\n  ...'

                if 'connection' in stderr.lower() or 'could not connect' in stderr.lower():
                    msg = (
                        'Database migration failed — could not connect to PostgreSQL.\n\n'
                        '  Ensure PostgreSQL is running and the connection string '
                        'is correct.\n\n'
                        '  To check:\n'
                        '    pg_isready -h localhost -p 5432\n'
                        '    linkedout config show          # verify database_url'
                    )
                else:
                    msg = (
                        'Database migration failed.\n\n'
                        f'  Details:\n    {stderr}'
                    )
                ctx.status = 'failed'
                ctx.detail = msg
            else:
                stdout = result.stdout.strip()
                migration_count = stdout.count('Running upgrade')
                ctx.extra = {'migrations_applied': migration_count}
                if migration_count == 0:
                    ctx.detail = 'No pending migrations'
                else:
                    ctx.detail = f'Applied {migration_count} migration(s)'

        assert ctx.result is not None
        if ctx.result.status == 'failed':
            raise UpgradeError(ctx.result.detail or 'Migration failed', ctx.result)
        return ctx.result

    def run_version_scripts(
        self,
        from_ver: str,
        to_ver: str,
    ) -> UpgradeStepResult:
        """Run version migration scripts for the given range."""
        with log_step(self.logger, 'version_scripts') as ctx:
            try:
                results = run_version_migrations(from_ver, to_ver, config=None)
                ctx.extra = {'scripts_run': len(results)}
                if not results:
                    ctx.status = 'skipped'
                    ctx.detail = f'No migration scripts for v{from_ver} -> v{to_ver}'
                else:
                    ctx.detail = f'Ran {len(results)} version migration script(s)'
            except Exception as exc:
                ctx.status = 'failed'
                ctx.detail = (
                    f'Version migration script failed.\n\n'
                    f'  Error: {exc}'
                )
                # Don't re-raise — let log_step close cleanly, then
                # we raise UpgradeError below based on ctx.result.status.
                # But log_step's except branch needs the exception to propagate
                # to set status=failed. So we need a different approach:
                # we already set ctx.status='failed', so the else branch will
                # pick it up correctly.

        assert ctx.result is not None
        if ctx.result.status == 'failed':
            raise UpgradeError(ctx.result.detail or 'Version scripts failed', ctx.result)
        return ctx.result

    def post_upgrade_check(self) -> UpgradeStepResult:
        """Run a basic health check after upgrade."""
        with log_step(self.logger, 'post_upgrade') as ctx:
            try:
                result = subprocess.run(
                    ['linkedout', 'status', '--json'],
                    capture_output=True,
                    text=True,
                    cwd=self.repo_root,
                )
                if result.returncode == 0:
                    ctx.detail = 'Health check passed'
                else:
                    ctx.status = 'success'  # non-blocking
                    ctx.detail = (
                        'Health check found issues.\n'
                        '  Run `linkedout diagnostics --repair` to investigate.'
                    )
            except FileNotFoundError:
                ctx.status = 'skipped'
                ctx.detail = 'Health check skipped (CLI not on PATH)'
            except Exception as exc:
                ctx.status = 'success'  # non-blocking
                ctx.detail = f'Health check could not run: {exc}'

        assert ctx.result is not None
        return ctx.result

    def update_extension(self, version: str) -> UpgradeStepResult | None:
        """Download the updated extension zip if the extension is installed.

        Returns an ``UpgradeStepResult`` on attempt, or ``None`` if skipped
        (extension not installed). Failures are non-blocking.
        """
        if not check_extension_installed():
            self.logger.debug('Extension not installed — skipping extension update')
            return None

        with log_step(self.logger, 'extension_update') as ctx:
            try:
                path = download_extension_zip(version)
                expected = fetch_expected_checksum(version)
                if expected is not None:
                    if not verify_checksum(path, expected):
                        ctx.status = 'failed'
                        ctx.detail = (
                            'Extension checksum verification failed.\n'
                            '  The downloaded file may be corrupted.\n'
                            '  You can retry with /linkedout-upgrade or download manually.'
                        )
                    else:
                        ctx.detail = (
                            f'Saved to {path}\n\n'
                            f'{get_sideload_instructions()}'
                        )
                else:
                    # No checksum available — accept the download
                    ctx.detail = (
                        f'Saved to {path}\n\n'
                        f'{get_sideload_instructions()}'
                    )
            except Exception as exc:
                ctx.status = 'failed'
                ctx.detail = (
                    f'Could not download the updated Chrome extension.\n\n'
                    f'  {exc}\n\n'
                    f'  The core upgrade succeeded — only the extension update was skipped.'
                )

        assert ctx.result is not None
        return ctx.result

    def show_whats_new(self, from_ver: str, to_ver: str) -> str:
        """Return formatted "What's New" content from the changelog."""
        return parse_changelog(from_ver, to_ver)

    def run_upgrade(self) -> UpgradeReport:
        """Orchestrate the full upgrade flow.

        Runs each step in order. On failure at any step, stops and produces
        a report with failure details and rollback instructions.

        Returns:
            An ``UpgradeReport`` with all step results and metadata.
        """
        overall_start = time.monotonic()
        steps: list[UpgradeStepResult] = []
        from_version = self._from_version
        to_version: str | None = None
        failures: list[str] = []

        self.logger.info('Starting upgrade from v{}', from_version)

        # Step 1: Pre-flight
        try:
            result = self.pre_flight_check()
            steps.append(result)
            if result.status == 'skipped':
                duration_ms = int((time.monotonic() - overall_start) * 1000)
                return UpgradeReport(
                    from_version=from_version,
                    to_version=from_version,
                    steps=steps,
                    duration_ms=duration_ms,
                )
            to_version = self._to_version
        except UpgradeError as exc:
            steps.append(exc.step_result)
            failures.append(str(exc))
            duration_ms = int((time.monotonic() - overall_start) * 1000)
            return UpgradeReport(
                from_version=from_version,
                to_version=from_version,
                steps=steps,
                duration_ms=duration_ms,
                failures=failures,
            )

        assert to_version is not None
        self.logger.info('Upgrading from v{} to v{}', from_version, to_version)

        # Steps 2-6: sequential, stop on failure
        step_sequence: list[tuple[str, object]] = [
            ('pull_code', self.pull_code),
            ('update_deps', self.update_deps),
            ('run_migrations', self.run_migrations),
            ('version_scripts', lambda: self.run_version_scripts(from_version, to_version)),
            ('post_upgrade', self.post_upgrade_check),
        ]

        for step_name, method in step_sequence:
            try:
                result = method()  # type: ignore[operator]
                steps.append(result)
            except UpgradeError as exc:
                steps.append(exc.step_result)
                failures.append(str(exc))
                duration_ms = int((time.monotonic() - overall_start) * 1000)
                rollback = self._rollback_instructions(from_version, step_name)
                report = UpgradeReport(
                    from_version=from_version,
                    to_version=to_version,
                    steps=steps,
                    duration_ms=duration_ms,
                    failures=failures,
                    rollback=rollback,
                )
                self._save_report(report)
                return report

        # Extension update (non-blocking)
        next_steps = ['Restart the backend if it was running: linkedout start-backend']
        ext_result = self.update_extension(to_version)
        if ext_result is not None:
            steps.append(ext_result)
            if ext_result.status == 'success':
                next_steps.append('Re-sideload the updated Chrome extension (see instructions above)')

        # What's New
        whats_new = self.show_whats_new(from_version, to_version)

        # Record the successful upgrade version
        self._save_last_upgrade_version(to_version)

        duration_ms = int((time.monotonic() - overall_start) * 1000)
        report = UpgradeReport(
            from_version=from_version,
            to_version=to_version,
            steps=steps,
            duration_ms=duration_ms,
            whats_new=whats_new,
            next_steps=next_steps,
        )
        self._save_report(report)
        self.logger.info(
            'Upgrade complete: v{} -> v{} ({}ms)',
            from_version,
            to_version,
            duration_ms,
        )
        return report

    def _rollback_instructions(self, from_version: str, failed_step: str) -> str:
        """Return rollback commands based on which step failed."""
        base = f'cd {self.repo_root}'
        checkout = f'git checkout v{from_version}'

        if failed_step == 'pull_code':
            return f'  {base}\n  git merge --abort  # if a merge is in progress'

        if failed_step == 'update_deps':
            return (
                f'  {base}\n'
                f'  {checkout}\n'
                f'  uv pip install -e "./backend[dev]"'
            )

        # migration or version_scripts — full rollback
        return (
            f'  {base}\n'
            f'  {checkout}\n'
            f'  uv pip install -e "./backend[dev]"\n'
            f'  linkedout migrate'
        )

    def _save_report(self, report: UpgradeReport) -> Path | None:
        """Write the upgrade report, handling errors gracefully."""
        try:
            return write_upgrade_report(report)
        except Exception:
            self.logger.error('Failed to write upgrade report')
            return None

    def _save_last_upgrade_version(self, version: str) -> None:
        """Record the last successfully upgraded version."""
        try:
            _STATE_DIR.mkdir(parents=True, exist_ok=True)
            _LAST_UPGRADE_FILE.write_text(version + '\n')
        except Exception:
            self.logger.warning('Could not save last upgrade version')
