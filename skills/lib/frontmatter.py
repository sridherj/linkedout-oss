"""Frontmatter processing for SKILL.md files.

Handles splitting, filtering, and rejoining YAML frontmatter according to
per-host rules (denylist/allowlist modes, description truncation).
"""

from __future__ import annotations

import re

import yaml


# Matches YAML frontmatter delimited by --- at the start of a file
_FRONTMATTER_RE = re.compile(r'\A---\n(.*?\n)---\n', re.DOTALL)


def split_frontmatter(content: str) -> tuple[str, str]:
    """Split a markdown file into frontmatter and body.

    Args:
        content: Full file content, optionally starting with ``---`` delimited
            YAML frontmatter.

    Returns:
        A ``(frontmatter, body)`` tuple.  *frontmatter* is the raw YAML string
        (without delimiters) or an empty string if none is present.  *body* is
        the remaining content.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return '', content
    frontmatter = match.group(1)
    body = content[match.end():]
    return frontmatter, body


def join_frontmatter(frontmatter: str, body: str) -> str:
    """Rejoin frontmatter and body with ``---`` delimiters.

    Args:
        frontmatter: Raw YAML string (without delimiters).  If empty, the body
            is returned as-is.
        body: Markdown body content.

    Returns:
        Combined string with frontmatter wrapped in ``---`` delimiters.
    """
    if not frontmatter.strip():
        return body
    # Ensure frontmatter ends with a newline
    if not frontmatter.endswith('\n'):
        frontmatter += '\n'
    return f'---\n{frontmatter}---\n{body}'


def process_frontmatter(frontmatter: str, host_config: dict) -> str:
    """Process YAML frontmatter according to host configuration rules.

    Applies the host's frontmatter rules:

    - **denylist** mode: removes fields listed in ``strip_fields``.
    - **allowlist** mode: keeps only fields listed in ``keep_fields``.
    - **description_limit**: truncates the ``description`` field to *N* characters.

    Args:
        frontmatter: Raw YAML frontmatter string (without ``---`` delimiters).
        host_config: Host configuration dictionary containing a ``frontmatter``
            key with mode and field rules.

    Returns:
        Processed YAML frontmatter string (without delimiters).
    """
    if not frontmatter.strip():
        return frontmatter

    data = yaml.safe_load(frontmatter)
    if not isinstance(data, dict):
        return frontmatter

    fm_config = host_config.get('frontmatter', {})
    mode = fm_config.get('mode', 'denylist')

    if mode == 'denylist':
        strip_fields = fm_config.get('strip_fields', [])
        for field in strip_fields:
            data.pop(field, None)
    elif mode == 'allowlist':
        keep_fields = set(fm_config.get('keep_fields', []))
        data = {k: v for k, v in data.items() if k in keep_fields}

    # Apply description length limit
    description_limit = fm_config.get('description_limit')
    if description_limit is not None and 'description' in data:
        desc = str(data['description'])
        if len(desc) > description_limit:
            data['description'] = desc[:description_limit]

    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
