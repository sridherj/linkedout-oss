# SPDX-License-Identifier: Apache-2.0
"""Tests for linkedout.query_history.session_manager — session lifecycle."""

import json
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    """Point LINKEDOUT_DATA_DIR to a temp directory."""
    monkeypatch.setenv('LINKEDOUT_DATA_DIR', str(tmp_path))
    return tmp_path


@pytest.fixture()
def session_file(data_dir):
    """Return the expected path of the active session file."""
    return data_dir / 'queries' / '.active_session.json'


class TestNewSessionCreation:
    """New session is created when no active session exists."""

    def test_creates_session_when_none_exists(self, data_dir, session_file):
        from linkedout.query_history.session_manager import get_or_create_session

        assert not session_file.exists()

        session_id, is_new = get_or_create_session('who works at Stripe?')
        assert is_new is True
        assert session_id.startswith('s_')
        assert session_file.exists()

    def test_session_file_has_required_fields(self, data_dir, session_file):
        from linkedout.query_history.session_manager import get_or_create_session

        get_or_create_session('who works at Stripe?')

        data = json.loads(session_file.read_text())
        required = {'session_id', 'initial_query', 'started_at', 'last_query_at', 'turn_count'}
        assert required.issubset(data.keys())
        assert data['initial_query'] == 'who works at Stripe?'
        assert data['turn_count'] == 1


class TestSessionContinuation:
    """Existing session is continued within timeout."""

    def test_continues_existing_session(self, data_dir, session_file):
        from linkedout.query_history.session_manager import get_or_create_session

        session_id_1, is_new_1 = get_or_create_session('first query')
        session_id_2, is_new_2 = get_or_create_session('follow-up query')

        assert is_new_1 is True
        assert is_new_2 is False
        assert session_id_1 == session_id_2

    def test_turn_count_increments(self, data_dir, session_file):
        from linkedout.query_history.session_manager import get_or_create_session

        get_or_create_session('first query')
        get_or_create_session('second query')
        get_or_create_session('third query')

        data = json.loads(session_file.read_text())
        assert data['turn_count'] == 3

    def test_last_query_at_updated(self, data_dir, session_file):
        from linkedout.query_history.session_manager import get_or_create_session

        get_or_create_session('first query')
        data_before = json.loads(session_file.read_text())

        get_or_create_session('second query')
        data_after = json.loads(session_file.read_text())

        assert data_after['last_query_at'] >= data_before['last_query_at']


class TestSessionTimeout:
    """New session is created when timeout expires."""

    def test_new_session_on_timeout(self, data_dir, session_file):
        from linkedout.query_history.session_manager import get_or_create_session

        session_id_1, _ = get_or_create_session('first query')

        # Manually set last_query_at to 31 minutes ago
        data = json.loads(session_file.read_text())
        past = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()
        data['last_query_at'] = past
        session_file.write_text(json.dumps(data))

        session_id_2, is_new = get_or_create_session('new query')
        assert is_new is True
        assert session_id_2 != session_id_1

    def test_session_continues_within_timeout(self, data_dir, session_file):
        from linkedout.query_history.session_manager import get_or_create_session

        session_id_1, _ = get_or_create_session('first query')

        # Set last_query_at to 29 minutes ago (within 30-minute default)
        data = json.loads(session_file.read_text())
        past = (datetime.now(timezone.utc) - timedelta(minutes=29)).isoformat()
        data['last_query_at'] = past
        session_file.write_text(json.dumps(data))

        session_id_2, is_new = get_or_create_session('follow-up')
        assert is_new is False
        assert session_id_2 == session_id_1


class TestStartNewSession:
    """start_new_session() always creates a new session."""

    def test_always_creates_new(self, data_dir, session_file):
        from linkedout.query_history.session_manager import start_new_session

        session_id_1 = start_new_session('query one')
        session_id_2 = start_new_session('query two')

        assert session_id_1 != session_id_2
        assert session_id_1.startswith('s_')
        assert session_id_2.startswith('s_')

    def test_overwrites_active_session(self, data_dir, session_file):
        from linkedout.query_history.session_manager import start_new_session

        start_new_session('query one')
        session_id_2 = start_new_session('query two')

        data = json.loads(session_file.read_text())
        assert data['session_id'] == session_id_2
        assert data['initial_query'] == 'query two'


class TestSessionIdPrefix:
    """session_id has s_ prefix."""

    def test_session_id_has_s_prefix(self, data_dir):
        from linkedout.query_history.session_manager import start_new_session

        session_id = start_new_session('test query')
        assert session_id.startswith('s_')
        assert len(session_id) > 3  # s_ plus nanoid


class TestSessionTimeoutEnvVar:
    """LINKEDOUT_SESSION_TIMEOUT_MINUTES env var override."""

    def test_custom_timeout_via_env_var(self, data_dir, session_file, monkeypatch):
        monkeypatch.setenv('LINKEDOUT_SESSION_TIMEOUT_MINUTES', '5')

        from linkedout.query_history.session_manager import get_or_create_session

        session_id_1, _ = get_or_create_session('first query')

        # Set last_query_at to 6 minutes ago (beyond 5-minute custom timeout)
        data = json.loads(session_file.read_text())
        past = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
        data['last_query_at'] = past
        session_file.write_text(json.dumps(data))

        session_id_2, is_new = get_or_create_session('new query')
        assert is_new is True
        assert session_id_2 != session_id_1


class TestGetActiveSession:
    """get_active_session() returns session data or None."""

    def test_returns_none_when_no_session(self, data_dir):
        from linkedout.query_history.session_manager import get_active_session

        assert get_active_session() is None

    def test_returns_session_data_after_creation(self, data_dir):
        from linkedout.query_history.session_manager import get_active_session, start_new_session

        session_id = start_new_session('test query')
        data = get_active_session()

        assert data is not None
        assert data['session_id'] == session_id
        assert data['initial_query'] == 'test query'

    def test_returns_none_on_corrupt_file(self, data_dir, session_file):
        from linkedout.query_history.session_manager import get_active_session

        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text('not valid json{{{')

        assert get_active_session() is None
