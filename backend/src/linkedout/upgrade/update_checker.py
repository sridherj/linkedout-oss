# SPDX-License-Identifier: Apache-2.0
"""GitHub Release update checker with local caching and snooze support.

Compares the local VERSION file against the latest GitHub Release tag.
Results are cached to ``~/linkedout-data/state/update-check.json`` to
avoid excessive API calls (max one per hour).

Snooze support allows users to dismiss update notifications with
escalating backoff intervals (24h → 48h → 1 week).
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from loguru import logger
from packaging.version import InvalidVersion, Version

from linkedout.version import __version__

GITHUB_REPO = 'sridherj/linkedout-oss'
GITHUB_API_URL = f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'
CACHE_FILE = Path.home() / 'linkedout-data' / 'state' / 'update-check.json'
SNOOZE_FILE = Path.home() / 'linkedout-data' / 'state' / 'update-snooze.json'
CACHE_MAX_AGE_SECONDS = 3600  # 1 hour

# Escalating snooze durations: count 1 → 24h, count 2 → 48h, count 3+ → 1 week
_SNOOZE_DURATIONS: dict[int, timedelta] = {
    1: timedelta(hours=24),
    2: timedelta(hours=48),
}
_SNOOZE_DEFAULT_DURATION = timedelta(weeks=1)


@dataclass(frozen=True)
class UpdateInfo:
    """Result of an update check."""

    latest_version: str
    current_version: str
    release_url: str
    is_outdated: bool
    checked_at: str


def check_for_update(*, force: bool = False, skip_snooze: bool = False, timeout: float = 10) -> UpdateInfo | None:
    """Check GitHub for a newer release, returning ``None`` on any error.

    Args:
        force: Skip cache freshness check, always hit GitHub API.
        skip_snooze: Return UpdateInfo even if snoozed (for --check).
        timeout: HTTP client timeout in seconds.
    """
    if not force:
        cached = get_cached_update()
        if cached is not None:
            info = cached
        else:
            try:
                info = _fetch_and_cache(timeout=timeout)
            except Exception:
                logger.debug('Update check failed — continuing without update info')
                return None
    else:
        try:
            info = _fetch_and_cache(timeout=timeout)
        except Exception:
            logger.debug('Update check failed — continuing without update info')
            return None

    if info is None or not info.is_outdated:
        return info

    # Reset snooze if a different (newer) version was detected
    _maybe_reset_snooze(info.latest_version)

    # Suppress notification if snoozed (unless caller asked to skip snooze)
    if not skip_snooze and is_snoozed(info.latest_version):
        return None

    return info


def _maybe_reset_snooze(latest_version: str) -> None:
    """Reset snooze if the snoozed version differs from *latest_version*."""
    try:
        if not SNOOZE_FILE.exists():
            return
        data = json.loads(SNOOZE_FILE.read_text())
        snoozed_ver = data.get('snoozed_version')
        if snoozed_ver and snoozed_ver != latest_version:
            reset_snooze()
    except Exception:
        pass


def get_cached_update() -> UpdateInfo | None:
    """Return cached update info if fresh (< 1 hour old), else ``None``."""
    try:
        if not CACHE_FILE.exists():
            return None
        data = json.loads(CACHE_FILE.read_text())
        checked_at = datetime.fromisoformat(data['checked_at'])
        age = (datetime.now(timezone.utc) - checked_at).total_seconds()
        if age >= CACHE_MAX_AGE_SECONDS:
            return None
        return UpdateInfo(
            latest_version=data['latest_version'],
            current_version=data['current_version'],
            release_url=data['release_url'],
            is_outdated=data['is_outdated'],
            checked_at=data['checked_at'],
        )
    except Exception:
        logger.debug('Could not read update cache')
        return None


def save_update_cache(info: UpdateInfo) -> None:
    """Write update info to the cache file."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(asdict(info), indent=2) + '\n')


# ── Snooze support ─────────────────────────────────────────


def is_snoozed(version: str) -> bool:
    """Return True if update notifications for *version* are snoozed.

    Reads ``~/linkedout-data/state/update-snooze.json``.
    Returns False on missing/corrupt file (treat as not snoozed).
    """
    try:
        if not SNOOZE_FILE.exists():
            return False
        data = json.loads(SNOOZE_FILE.read_text())
        if data.get('snoozed_version') != version:
            return False
        next_reminder = datetime.fromisoformat(data['next_reminder'])
        return datetime.now(timezone.utc) < next_reminder
    except Exception:
        logger.debug('Could not read snooze state — treating as not snoozed')
        return False


def snooze_update(version: str) -> None:
    """Snooze update notifications for *version* with escalating backoff.

    Escalation: first snooze → +24h, second → +48h, third+ → +1 week.
    State is persisted to ``~/linkedout-data/state/update-snooze.json``.
    """
    snooze_count = 0
    try:
        if SNOOZE_FILE.exists():
            data = json.loads(SNOOZE_FILE.read_text())
            if data.get('snoozed_version') == version:
                snooze_count = data.get('snooze_count', 0)
    except Exception:
        pass

    snooze_count += 1
    duration = _SNOOZE_DURATIONS.get(snooze_count, _SNOOZE_DEFAULT_DURATION)
    now = datetime.now(timezone.utc)

    state = {
        'snoozed_at': now.isoformat(),
        'snooze_count': snooze_count,
        'next_reminder': (now + duration).isoformat(),
        'snoozed_version': version,
    }
    SNOOZE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SNOOZE_FILE.write_text(json.dumps(state, indent=2) + '\n')


def get_snooze_duration(version: str) -> timedelta:
    """Return the duration of the next snooze for display purposes.

    Reads the current snooze count for *version* and computes what the
    next snooze duration would be. Returns the default (24h) if no
    prior snooze exists.
    """
    snooze_count = 0
    try:
        if SNOOZE_FILE.exists():
            data = json.loads(SNOOZE_FILE.read_text())
            if data.get('snoozed_version') == version:
                snooze_count = data.get('snooze_count', 0)
    except Exception:
        pass

    next_count = snooze_count + 1
    return _SNOOZE_DURATIONS.get(next_count, _SNOOZE_DEFAULT_DURATION)


def reset_snooze() -> None:
    """Clear the snooze state.

    Called when a new version is detected (different from the snoozed version).
    """
    try:
        if SNOOZE_FILE.exists():
            SNOOZE_FILE.unlink()
    except Exception:
        logger.debug('Could not clear snooze state')


def _fetch_and_cache(timeout: float = 10) -> UpdateInfo | None:
    """Hit the GitHub API, build an UpdateInfo, cache it, and return it."""
    headers = {'Accept': 'application/vnd.github+json'}
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'

    with httpx.Client(timeout=timeout) as client:
        resp = client.get(GITHUB_API_URL, headers=headers)
        resp.raise_for_status()

    data = resp.json()
    tag = data.get('tag_name', '')
    # Strip leading 'v' if present (e.g. "v0.2.0" -> "0.2.0")
    latest_str = tag.lstrip('v')
    release_url = data.get('html_url', f'https://github.com/{GITHUB_REPO}/releases')

    is_outdated = _is_outdated(__version__, latest_str)
    now = datetime.now(timezone.utc).isoformat()

    info = UpdateInfo(
        latest_version=latest_str,
        current_version=__version__,
        release_url=release_url,
        is_outdated=is_outdated,
        checked_at=now,
    )
    save_update_cache(info)
    return info


def _is_outdated(current: str, latest: str) -> bool:
    """Return True if *latest* is strictly newer than *current*.

    Uses ``packaging.version.Version`` for robust PEP 440 comparison.
    Returns False on parse errors (treat unparseable as not-outdated).
    """
    try:
        return Version(latest) > Version(current)
    except InvalidVersion:
        logger.debug(f'Could not parse versions: current={current!r}, latest={latest!r}')
        return False
