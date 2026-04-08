"""Skill template engine and host configuration library.

Public API:

- :func:`render_template` -- render a template string with variable substitution
  and conditional blocks.
- :func:`load_host_config` -- load a per-host YAML configuration.
- :func:`get_global_context` -- return global template variables (version, paths).
- :func:`process_frontmatter` -- filter YAML frontmatter per host rules.
"""

from skills.lib.config import get_global_context, load_host_config
from skills.lib.frontmatter import process_frontmatter
from skills.lib.template import render_template

__all__ = [
    'render_template',
    'load_host_config',
    'get_global_context',
    'process_frontmatter',
]
