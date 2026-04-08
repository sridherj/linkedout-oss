# SPDX-License-Identifier: Apache-2.0
"""Parse CHANGELOG.md to extract "What's New" content between versions.

Expects `Keep a Changelog <https://keepachangelog.com/>`_ format with
``## [X.Y.Z]`` section headers.  Extracts bullet items between two
version boundaries, flattening category headers (``### Added``, etc.)
into a single list per version.
"""
from __future__ import annotations

import re
from pathlib import Path

from packaging.version import InvalidVersion, Version

GITHUB_REPO = 'sridherj/linkedout-oss'
_VERSION_HEADER_RE = re.compile(r'^## \[(\d+\.\d+\.\d+[^\]]*)\]')
_CATEGORY_HEADER_RE = re.compile(r'^### ')
_MAX_DISPLAY_LINES = 30
_TRUNCATE_SHOW = 25


def _repo_root() -> Path:
    """Return the repository root (parent of ``backend/``)."""
    return Path(__file__).resolve().parent.parent.parent.parent


def parse_changelog(
    old_version: str,
    new_version: str,
    *,
    changelog_path: Path | None = None,
) -> str:
    """Extract changelog content between *old_version* and *new_version*.

    Returns a formatted string suitable for terminal display, or a
    fallback message when the changelog is missing / versions not found.

    Args:
        old_version: The version the user is upgrading *from* (exclusive).
        new_version: The version the user is upgrading *to* (inclusive).
        changelog_path: Override the path to CHANGELOG.md (for testing).
    """
    path = changelog_path or (_repo_root() / 'CHANGELOG.md')

    if not path.exists() or path.stat().st_size == 0:
        return _fallback(new_version, 'No changelog entries found.')

    text = path.read_text(encoding='utf-8')
    sections = _extract_sections(text, old_version, new_version)

    if not sections:
        return _fallback(new_version, 'Changelog entry not found for this version.')

    if len(sections) == 1:
        return _format_single(new_version, sections[0][1])
    return _format_multi(old_version, sections)


def _extract_sections(
    text: str,
    old_version: str,
    new_version: str,
) -> list[tuple[str, list[str]]]:
    """Return ``[(version, [bullet_lines]), ...]`` newest-first for versions
    in the range ``(old_version, new_version]``.
    """
    try:
        old_ver = Version(old_version)
        new_ver = Version(new_version)
    except InvalidVersion:
        return []

    # Parse all version sections
    all_sections: list[tuple[str, list[str]]] = []
    current_ver: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        m = _VERSION_HEADER_RE.match(line)
        if m:
            if current_ver is not None:
                all_sections.append((current_ver, current_lines))
            current_ver = m.group(1)
            current_lines = []
            continue
        if current_ver is not None:
            # Skip category headers, keep bullet lines and non-empty content
            if _CATEGORY_HEADER_RE.match(line):
                continue
            stripped = line.strip()
            if stripped:
                current_lines.append(stripped)

    # Don't forget the last section
    if current_ver is not None:
        all_sections.append((current_ver, current_lines))

    # Filter to versions in range (old_version, new_version]
    result = []
    for ver_str, lines in all_sections:
        try:
            v = Version(ver_str)
        except InvalidVersion:
            continue
        if old_ver < v <= new_ver and lines:
            result.append((ver_str, lines))

    # Newest first
    result.sort(key=lambda x: Version(x[0]), reverse=True)
    return result


def _format_single(new_version: str, lines: list[str]) -> str:
    """Format a single-version What's New block."""
    header = f"What's New in v{new_version}"
    separator = '-' * len(header)
    body_lines = _ensure_bullets(lines)
    body = '\n'.join(body_lines)
    full = f'{header}\n{separator}\n{body}'
    return _maybe_truncate(full)


def _format_multi(old_version: str, sections: list[tuple[str, list[str]]]) -> str:
    """Format a multi-version What's New block."""
    header = f"What's New since v{old_version}"
    separator = '-' * len(header)
    parts = [f'{header}\n{separator}']
    for ver_str, lines in sections:
        bullet_lines = _ensure_bullets(lines)
        parts.append(f'\nv{ver_str}:\n' + '\n'.join(bullet_lines))
    full = '\n'.join(parts)
    return _maybe_truncate(full)


def _ensure_bullets(lines: list[str]) -> list[str]:
    """Ensure each line starts with ``- ``."""
    result = []
    for line in lines:
        if not line.startswith('- '):
            line = f'- {line}'
        result.append(line)
    return result


def _maybe_truncate(text: str) -> str:
    """Truncate if more than ``_MAX_DISPLAY_LINES`` lines of content."""
    lines = text.split('\n')
    if len(lines) <= _MAX_DISPLAY_LINES:
        return text
    truncated = lines[:_TRUNCATE_SHOW]
    remaining = len(lines) - _TRUNCATE_SHOW
    truncated.append(
        f'  ... and {remaining} more changes. See full changelog:\n'
        f'  https://github.com/{GITHUB_REPO}/blob/main/CHANGELOG.md'
    )
    return '\n'.join(truncated)


def _fallback(new_version: str, reason: str) -> str:
    """Return a fallback What's New block."""
    header = f"What's New in v{new_version}"
    separator = '-' * len(header)
    url = f'https://github.com/{GITHUB_REPO}/releases/tag/v{new_version}'
    return f'{header}\n{separator}\n  {reason} See {url}'
