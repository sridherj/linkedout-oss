# SPDX-License-Identifier: Apache-2.0
"""Tests for snooze support in update_checker."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from linkedout.upgrade.update_checker import (
    UpdateInfo,
    check_for_update,
    get_snooze_duration,
    is_snoozed,
    reset_snooze,
    snooze_update,
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


class TestGetSnoozeDuration:
    """get_snooze_duration returns the *next* snooze duration for display."""

    def test_first_snooze_returns_24h(self, snooze_file):
        assert get_snooze_duration('0.2.0') == timedelta(hours=24)

    def test_second_snooze_returns_48h(self, snooze_file):
        snooze_update('0.2.0')
        assert get_snooze_duration('0.2.0') == timedelta(hours=48)

    def test_third_snooze_returns_1_week(self, snooze_file):
        snooze_update('0.2.0')
        snooze_update('0.2.0')
        assert get_snooze_duration('0.2.0') == timedelta(weeks=1)

    def test_different_version_resets_to_24h(self, snooze_file):
        snooze_update('0.2.0')
        snooze_update('0.2.0')
        # Asking about a different version — count resets
        assert get_snooze_duration('0.3.0') == timedelta(hours=24)


class TestSnoozeCliFlag:
    """CLI --snooze flag invokes snooze workflow."""

    def test_snooze_outdated_version(self, snooze_file):
        from click.testing import CliRunner

        from linkedout.commands.upgrade import upgrade_command

        info = _make_update_info(latest='0.3.0', current='0.1.0', is_outdated=True)
        runner = CliRunner()
        with patch('linkedout.upgrade.update_checker.check_for_update', return_value=info) as mock_check, \
             patch('linkedout.upgrade.update_checker.snooze_update') as mock_snooze, \
             patch('linkedout.upgrade.update_checker.get_snooze_duration', return_value=timedelta(hours=24)), \
             patch('linkedout.upgrade.update_checker.get_cached_update'):
            result = runner.invoke(upgrade_command, ['--snooze'])

        assert result.exit_code == 0
        assert 'Update v0.3.0 snoozed for 24 hours' in result.output
        mock_check.assert_called_once_with(skip_snooze=True)
        mock_snooze.assert_called_once_with('0.3.0')

    def test_snooze_up_to_date(self, snooze_file):
        from click.testing import CliRunner

        from linkedout.commands.upgrade import upgrade_command

        info = _make_update_info(latest='0.1.0', current='0.1.0', is_outdated=False)
        runner = CliRunner()
        with patch('linkedout.upgrade.update_checker.check_for_update', return_value=info), \
             patch('linkedout.upgrade.update_checker.get_cached_update'):
            result = runner.invoke(upgrade_command, ['--snooze'])

        assert result.exit_code == 0
        assert 'Already running the latest version.' in result.output

    def test_snooze_network_error(self, snooze_file):
        from click.testing import CliRunner

        from linkedout.commands.upgrade import upgrade_command

        runner = CliRunner()
        with patch('linkedout.upgrade.update_checker.check_for_update', return_value=None), \
             patch('linkedout.upgrade.update_checker.get_cached_update', return_value=None):
            result = runner.invoke(upgrade_command, ['--snooze'])

        assert result.exit_code == 0
        assert 'Could not check for updates.' in result.output

    def test_snooze_already_snoozed_shows_increased_duration(self, snooze_file):
        from click.testing import CliRunner

        from linkedout.commands.upgrade import upgrade_command

        info = _make_update_info(latest='0.3.0', current='0.1.0', is_outdated=True)
        # Pre-snooze once so next duration is 48h
        snooze_update('0.3.0')

        runner = CliRunner()
        with patch('linkedout.upgrade.update_checker.check_for_update', return_value=info), \
             patch('linkedout.upgrade.update_checker.get_cached_update'):
            result = runner.invoke(upgrade_command, ['--snooze'])

        assert result.exit_code == 0
        assert 'snoozed for 48 hours' in result.output
