"""Template engine for rendering SKILL.md.tmpl files into host-specific SKILL.md files.

Supports variable substitution (``{{VARIABLE_NAME}}``) and simple conditional
blocks (``{{#if HOST_NAME == "claude"}}...{{/if}}``).  No external dependencies
beyond the Python standard library.
"""

from __future__ import annotations

import re
from pathlib import Path


# Matches {{#if VAR == "value"}} or {{#if VAR != "value"}}
_CONDITIONAL_RE = re.compile(
    r'\{\{#if\s+(\w+)\s*(==|!=)\s*"([^"]*)"\s*\}\}'
    r'(.*?)'
    r'\{\{/if\}\}',
    re.DOTALL,
)

# Matches {{VARIABLE_NAME}} (but not {{#if or {{/if}})
_VARIABLE_RE = re.compile(r'\{\{(?!#if|/if)([A-Z_][A-Z0-9_]*)\}\}')


def load_template(path: str) -> str:
    """Read a ``.tmpl`` file and return its content as a string.

    Args:
        path: Filesystem path to the template file.

    Raises:
        FileNotFoundError: If *path* does not exist.
    """
    return Path(path).read_text(encoding='utf-8')


def _resolve_conditionals(template: str, variables: dict[str, str]) -> str:
    """Evaluate all ``{{#if …}}`` / ``{{/if}}`` blocks."""

    def _replace_conditional(match: re.Match[str]) -> str:
        var_name = match.group(1)
        operator = match.group(2)
        compare_value = match.group(3)
        body = match.group(4)

        actual = variables.get(var_name, '')
        if operator == '==':
            return body if actual == compare_value else ''
        # operator == '!='
        return body if actual != compare_value else ''

    # Repeat until no more conditionals (handles sequential, not nested)
    prev = None
    result = template
    while result != prev:
        prev = result
        result = _CONDITIONAL_RE.sub(_replace_conditional, result)
    return result


def _resolve_variables(template: str, variables: dict[str, str]) -> str:
    """Replace all ``{{VARIABLE_NAME}}`` placeholders.

    Raises:
        ValueError: If any variable reference cannot be resolved.
    """
    unresolved: list[str] = []

    def _replace_var(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in variables:
            return variables[name]
        unresolved.append(name)
        return match.group(0)  # keep original for error message

    result = _VARIABLE_RE.sub(_replace_var, template)
    if unresolved:
        names = ', '.join(sorted(set(unresolved)))
        raise ValueError(f'Unresolved template variables: {names}')
    return result


def render_template(template: str, variables: dict[str, str]) -> str:
    """Render a template string by resolving conditionals and variables.

    Args:
        template: Template content with ``{{VAR}}`` and ``{{#if …}}`` blocks.
        variables: Mapping of variable names to their string values.

    Returns:
        Fully rendered string.

    Raises:
        ValueError: If any ``{{VAR}}`` reference has no matching key in *variables*.
    """
    result = _resolve_conditionals(template, variables)
    result = _resolve_variables(result, variables)
    return result


def render_template_file(
    tmpl_path: str,
    host_config: dict,
    global_context: dict,
) -> str:
    """Load a template file and render it with merged host + global variables.

    This is the main entry point for the full render pipeline:
    load template -> merge variables -> resolve conditionals -> resolve variables.

    Args:
        tmpl_path: Path to the ``.tmpl`` file.
        host_config: Host configuration dictionary (from ``load_host_config``).
        global_context: Global context dictionary (from ``get_global_context``).

    Returns:
        Fully rendered string.
    """
    from skills.lib.config import get_host_variables

    template = load_template(tmpl_path)
    variables = get_host_variables(host_config, global_context)
    return render_template(template, variables)
