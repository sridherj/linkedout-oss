# SPDX-License-Identifier: Apache-2.0
"""Session management for grouping related queries into conversations.

Sessions are stored as a single JSON file at ~/linkedout-data/queries/.active_session.json.
A session expires after a configurable timeout (default 30 minutes), at which point the
next query starts a new session automatically.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from nanoid import generate as nanoid_generate


def _get_queries_dir() -> Path:
    """Resolve the queries directory, respecting LINKEDOUT_DATA_DIR override."""
    data_dir = os.environ.get('LINKEDOUT_DATA_DIR', os.path.expanduser('~/linkedout-data'))
    return Path(os.path.expanduser(data_dir)) / 'queries'


def _get_session_file() -> Path:
    """Resolve the active session file path."""
    return _get_queries_dir() / '.active_session.json'


def _get_timeout_minutes() -> int:
    """Get session timeout from env var or default."""
    try:
        return int(os.environ.get('LINKEDOUT_SESSION_TIMEOUT_MINUTES', '30'))
    except ValueError:
        return 30


def _generate_session_id() -> str:
    """Generate a session ID with s_ prefix."""
    return f's_{nanoid_generate()}'


def _now() -> datetime:
    """Current UTC time."""
    return datetime.now(timezone.utc)


def start_new_session(query_text: str) -> str:
    """Create a new session unconditionally.

    Args:
        query_text: The initial query text for this session.

    Returns:
        The new session_id.
    """
    session_id = _generate_session_id()
    now = _now().isoformat()

    session_data = {
        'session_id': session_id,
        'initial_query': query_text,
        'started_at': now,
        'last_query_at': now,
        'turn_count': 1,
    }

    session_file = _get_session_file()
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(json.dumps(session_data, indent=2) + '\n')

    return session_id


def get_active_session() -> dict | None:
    """Return the current active session data, or None if no session file exists."""
    session_file = _get_session_file()
    if not session_file.exists():
        return None
    try:
        return json.loads(session_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def get_or_create_session(query_text: str, timeout_minutes: int = 0) -> tuple[str, bool]:
    """Get existing session or create a new one if expired/missing.

    Args:
        query_text: The query text (used as initial_query for new sessions).
        timeout_minutes: Session timeout in minutes. 0 means use env var or default (30).

    Returns:
        Tuple of (session_id, is_new_session).
    """
    if timeout_minutes <= 0:
        timeout_minutes = _get_timeout_minutes()

    session = get_active_session()

    if session is None:
        return start_new_session(query_text), True

    # Check if session has timed out
    try:
        last_query_at = datetime.fromisoformat(session['last_query_at'])
    except (KeyError, ValueError):
        return start_new_session(query_text), True

    elapsed_minutes = (_now() - last_query_at).total_seconds() / 60.0
    if elapsed_minutes > timeout_minutes:
        return start_new_session(query_text), True

    # Update existing session
    session['last_query_at'] = _now().isoformat()
    session['turn_count'] = session.get('turn_count', 0) + 1

    session_file = _get_session_file()
    session_file.write_text(json.dumps(session, indent=2) + '\n')

    return session['session_id'], False
