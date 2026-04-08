# SPDX-License-Identifier: Apache-2.0
"""Tests for snooze support and auto-upgrade in update_checker."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from linkedout.upgrade.update_checker import (
    UpdateInfo,
    check_for_update,
    is_snoozed,
    reset_snooze,
    snooze_update,
    try_auto_upgrade,
)


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
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture()
def snooze_file(tmp_path):
    """Redirect the snooze file to a temp directory."""
    path = tmp_path / 'state' / 'update-snooze.json'
    with patch('linkedout.upgrade.update_checker.SNOOZE_FILE', path):
        yield path


@pytest.fixture()
def cache_file(tmp_path):
    """Redirect the cache file to a temp directory."""
    path = tmp_path / 'state' / 'update-check.json'
    with patch('linkedout.upgrade.update_checker.CACHE_FILE', path):
        yield path


class TestSnoozeEscalation:
    """Snooze durations escalate: 24h -> 48h -> 1 week."""

    def test_first_snooze_24h(self, snooze_file):
        snooze_update('0.2.0')
        data = json.loads(snooze_file.read_text())
        assert data['snooze_count'] == 1
        snoozed_at = datetime.fromisoformat(data['snoozed_at'])
        next_reminder = datetime.fromisoformat(data['next_reminder'])
        delta = next_reminder - snoozed_at
        assert timedelta(hours=23, minutes=59) < delta <= timedelta(hours=24, seconds=1)

    def test_second_snooze_48h(self, snooze_file):
        snooze_update('0.2.0')
        snooze_update('0.2.0')
        data = json.loads(snooze_file.read_text())
        assert data['snooze_count'] == 2
        snoozed_at = datetime.fromisoformat(data['snoozed_at'])
        next_reminder = datetime.fromisoformat(data['next_reminder'])
        delta = next_reminder - snoozed_at
        assert timedelta(hours=47, minutes=59) < delta <= timedelta(hours=48, seconds=1)

    def test_third_snooze_1_week(self, snooze_file):
        snooze_update('0.2.0')
        snooze_update('0.2.0')
        snooze_update('0.2.0')
        data = json.loads(snooze_file.read_text())
        assert data['snooze_count'] == 3
        snoozed_at = datetime.fromisoformat(data['snoozed_at'])
        next_reminder = datetime.fromisoformat(data['next_reminder'])
        delta = next_reminder - snoozed_at
        assert timedelta(days=6, hours=23, minutes=59) < delta <= timedelta(weeks=1, seconds=1)

    def test_fourth_snooze_still_1_week(self, snooze_file):
        for _ in range(4):
            snooze_update('0.2.0')
        data = json.loads(snooze_file.read_text())
        assert data['snooze_count'] == 4
        snoozed_at = datetime.fromisoformat(data['snoozed_at'])
        next_reminder = datetime.fromisoformat(data['next_reminder'])
        delta = next_reminder - snoozed_at
        assert timedelta(days=6, hours=23, minutes=59) < delta <= timedelta(weeks=1, seconds=1)


class TestIsSnoozed:
    """is_snoozed returns True within snooze window, False after."""

    def test_returns_true_within_window(self, snooze_file):
        snooze_update('0.2.0')
        assert is_snoozed('0.2.0') is True

    def test_returns_false_after_expiry(self, snooze_file):
        snooze_update('0.2.0')
        # Manually set next_reminder to the past
        data = json.loads(snooze_file.read_text())
        data['next_reminder'] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        snooze_file.write_text(json.dumps(data))
        assert is_snoozed('0.2.0') is False

    def test_returns_false_for_different_version(self, snooze_file):
        snooze_update('0.2.0')
        assert is_snoozed('0.3.0') is False

    def test_returns_false_when_no_file(self, snooze_file):
        assert is_snoozed('0.2.0') is False

    def test_returns_false_on_corrupt_file(self, snooze_file):
        snooze_file.parent.mkdir(parents=True, exist_ok=True)
        snooze_file.write_text('not valid json!!!')
        assert is_snoozed('0.2.0') is False


class TestResetSnooze:
    """Snooze resets when new version detected."""

    def test_reset_deletes_file(self, snooze_file):
        snooze_update('0.2.0')
        assert snooze_file.exists()
        reset_snooze()
        assert not snooze_file.exists()

    def test_reset_when_no_file_is_noop(self, snooze_file):
        reset_snooze()  # Should not raise

    def test_snooze_resets_on_new_version(self, snooze_file):
        """Snoozed v0.2.0, but v0.3.0 now available — snooze resets."""
        snooze_update('0.2.0')
        assert is_snoozed('0.2.0') is True
        # Different version should not match
        assert is_snoozed('0.3.0') is False


class TestSnoozePersistence:
    """Snooze state persists across calls (read/write round-trip)."""

    def test_state_round_trip(self, snooze_file):
        snooze_update('0.2.0')
        data = json.loads(snooze_file.read_text())
        assert data['snoozed_version'] == '0.2.0'
        assert data['snooze_count'] == 1
        assert 'snoozed_at' in data
        assert 'next_reminder' in data

    def test_count_increments_across_calls(self, snooze_file):
        snooze_update('0.2.0')
        snooze_update('0.2.0')
        snooze_update('0.2.0')
        data = json.loads(snooze_file.read_text())
        assert data['snooze_count'] == 3


class TestCheckForUpdateWithSnooze:
    """check_for_update() respects snooze state."""

    def test_returns_none_when_snoozed(self, snooze_file, cache_file):
        """Snoozed version → check_for_update returns None."""
        snooze_update('0.2.0')

        info = _make_update_info(latest='0.2.0', current='0.1.0', is_outdated=True)
        with patch('linkedout.upgrade.update_checker.get_cached_update', return_value=info):
            result = check_for_update()

        assert result is None

    def test_returns_info_when_not_snoozed(self, snooze_file, cache_file):
        """No snooze → check_for_update returns the update info."""
        info = _make_update_info(latest='0.2.0', current='0.1.0', is_outdated=True)
        with patch('linkedout.upgrade.update_checker.get_cached_update', return_value=info):
            result = check_for_update()

        assert result is not None
        assert result.latest_version == '0.2.0'

    def test_resets_snooze_on_new_version(self, snooze_file, cache_file):
        """Snoozed v0.2.0, but v0.3.0 now available → snooze resets, returns info."""
        snooze_update('0.2.0')

        info = _make_update_info(latest='0.3.0', current='0.1.0', is_outdated=True)
        with patch('linkedout.upgrade.update_checker.get_cached_update', return_value=info):
            result = check_for_update()

        # Snooze was for 0.2.0, new version is 0.3.0 — should reset and return
        assert result is not None
        assert result.latest_version == '0.3.0'
        assert not snooze_file.exists()

    def test_not_outdated_returns_as_is(self, snooze_file, cache_file):
        """Not outdated → returns info regardless of snooze state."""
        info = _make_update_info(latest='0.1.0', current='0.1.0', is_outdated=False)
        with patch('linkedout.upgrade.update_checker.get_cached_update', return_value=info):
            result = check_for_update()

        assert result is not None
        assert result.is_outdated is False


class TestAutoUpgradeConfig:
    """auto_upgrade config flag is read correctly from LinkedOutSettings."""

    def test_default_is_false(self):
        from shared.config.settings import LinkedOutSettings

        settings = LinkedOutSettings(database_url='postgresql://test:test@localhost/test')
        assert settings.auto_upgrade is False

    def test_can_enable(self):
        from shared.config.settings import LinkedOutSettings

        settings = LinkedOutSettings(
            database_url='postgresql://test:test@localhost/test',
            auto_upgrade=True,
        )
        assert settings.auto_upgrade is True


class TestTryAutoUpgrade:
    """Auto-upgrade triggers silent upgrade and falls back on failure."""

    def test_success_returns_true(self, tmp_path):
        log_file = tmp_path / 'logs' / 'cli.log'
        info = _make_update_info()

        with patch('linkedout.upgrade.update_checker.LOG_FILE', log_file), \
             patch('linkedout.version._repo_root', return_value=tmp_path), \
             patch('subprocess.run') as mock_run:
            # Both git pull and uv pip install succeed
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
            result = try_auto_upgrade(info)

        assert result is True
        assert log_file.exists()
        log_content = log_file.read_text()
        assert 'Auto-upgrade completed successfully' in log_content

    def test_git_pull_failure_returns_false(self, tmp_path):
        log_file = tmp_path / 'logs' / 'cli.log'
        info = _make_update_info()

        with patch('linkedout.upgrade.update_checker.LOG_FILE', log_file), \
             patch('linkedout.version._repo_root', return_value=tmp_path), \
             patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='merge conflict')
            result = try_auto_upgrade(info)

        assert result is False
        log_content = log_file.read_text()
        assert 'git pull failed' in log_content

    def test_dep_update_failure_returns_false(self, tmp_path):
        log_file = tmp_path / 'logs' / 'cli.log'
        info = _make_update_info()

        def side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get('args', [])
            if cmd[0] == 'git':
                return MagicMock(returncode=0, stdout='', stderr='')
            return MagicMock(returncode=1, stdout='', stderr='resolution failed')

        with patch('linkedout.upgrade.update_checker.LOG_FILE', log_file), \
             patch('linkedout.version._repo_root', return_value=tmp_path), \
             patch('subprocess.run', side_effect=side_effect):
            result = try_auto_upgrade(info)

        assert result is False
        log_content = log_file.read_text()
        assert 'dep update failed' in log_content

    def test_logs_to_file_not_terminal(self, tmp_path, capsys):
        log_file = tmp_path / 'logs' / 'cli.log'
        info = _make_update_info()

        with patch('linkedout.upgrade.update_checker.LOG_FILE', log_file), \
             patch('linkedout.version._repo_root', return_value=tmp_path), \
             patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
            try_auto_upgrade(info)

        captured = capsys.readouterr()
        assert captured.out == ''  # No terminal output
        assert log_file.exists()  # Logged to file

    def test_exception_returns_false(self, tmp_path):
        log_file = tmp_path / 'logs' / 'cli.log'
        info = _make_update_info()

        with patch('linkedout.upgrade.update_checker.LOG_FILE', log_file), \
             patch('linkedout.version._repo_root', side_effect=RuntimeError('boom')):
            result = try_auto_upgrade(info)

        assert result is False
