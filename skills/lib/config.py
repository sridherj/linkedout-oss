"""Host configuration loader and global template context.

Loads per-host YAML configs from ``skills/hosts/`` and provides the global
variables shared across all templates (version, paths, CLI prefix).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml


# Root of the repository — two levels up from skills/lib/
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_HOSTS_DIR = _REPO_ROOT / 'skills' / 'hosts'

_REQUIRED_HOST_FIELDS = (
    'name',
    'display_name',
    'skill_install_path',
    'local_skill_path',
    'frontmatter',
    'path_rewrites',
    'tool_rewrites',
)


def load_host_config(host_name: str) -> dict:
    """Load and validate a host configuration from ``skills/hosts/{host_name}.yaml``.

    Args:
        host_name: Host identifier (e.g. ``"claude"``, ``"codex"``, ``"copilot"``).

    Returns:
        Parsed host configuration dictionary.

    Raises:
        FileNotFoundError: If the host config file does not exist.
        ValueError: If required fields are missing.
    """
    config_path = _HOSTS_DIR / f'{host_name}.yaml'
    if not config_path.exists():
        available = ', '.join(list_hosts()) or '(none)'
        raise FileNotFoundError(
            f'Host config not found: {config_path}. Available hosts: {available}'
        )

    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f'Host config {config_path} must be a YAML mapping, got {type(config).__name__}')

    missing = [field for field in _REQUIRED_HOST_FIELDS if field not in config]
    if missing:
        raise ValueError(
            f'Host config {host_name!r} missing required fields: {", ".join(missing)}'
        )

    return config


def list_hosts() -> list[str]:
    """Return sorted list of available host names by scanning ``skills/hosts/*.yaml``."""
    if not _HOSTS_DIR.is_dir():
        return []
    return sorted(p.stem for p in _HOSTS_DIR.glob('*.yaml'))


def _read_version() -> str:
    """Read the project version from ``backend/pyproject.toml``."""
    pyproject_path = _REPO_ROOT / 'backend' / 'pyproject.toml'
    if pyproject_path.exists():
        content = pyproject_path.read_text(encoding='utf-8')
        match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        if match:
            return match.group(1)

    # Fallback: VERSION file at repo root
    version_path = _REPO_ROOT / 'VERSION'
    if version_path.exists():
        return version_path.read_text(encoding='utf-8').strip()

    return '0.0.0'


def _read_schema_snippet() -> str:
    """Read the auto-generated schema reference for inclusion in skill templates."""
    schema_path = _REPO_ROOT / 'skills' / 'linkedout' / 'schema-reference.md'
    if schema_path.exists():
        content = schema_path.read_text(encoding='utf-8')
        # Strip the auto-generated header comment
        lines = content.split('\n')
        stripped = [l for l in lines if not l.startswith('<!-- Auto-generated')]
        return '\n'.join(stripped).strip()
    return '*(Schema reference not available — run `bin/generate-schema-ref` to generate.)*'


def get_global_context() -> dict[str, str]:
    """Return global template variables shared across all hosts.

    Returns:
        Dictionary with keys: ``VERSION``, ``DATA_DIR``, ``CONFIG_DIR``,
        ``CLI_PREFIX``, ``AGENT_CONTEXT_PATH``, ``DB_SCHEMA_SNIPPET``.
    """
    return {
        'VERSION': _read_version(),
        'DATA_DIR': '~/linkedout-data/',
        'CONFIG_DIR': '~/linkedout-data/config/',
        'CLI_PREFIX': 'linkedout',
        'AGENT_CONTEXT_PATH': '~/linkedout-data/config/agent-context.env',
        'DB_SCHEMA_SNIPPET': _read_schema_snippet(),
    }


def get_host_variables(host_config: dict, global_context: dict) -> dict[str, str]:
    """Merge host-specific variables with global context.

    Adds ``HOST_NAME``, ``DISPLAY_NAME``, ``SKILL_INSTALL_PATH``, and
    ``LOCAL_SKILL_PATH`` from the host config on top of the global context.

    Args:
        host_config: Parsed host configuration (from ``load_host_config``).
        global_context: Global variables (from ``get_global_context``).

    Returns:
        Merged variable dictionary ready for template rendering.
    """
    variables = dict(global_context)
    variables['HOST_NAME'] = host_config['name']
    variables['DISPLAY_NAME'] = host_config['display_name']
    variables['SKILL_INSTALL_PATH'] = host_config['skill_install_path']
    variables['LOCAL_SKILL_PATH'] = host_config['local_skill_path']
    return variables
