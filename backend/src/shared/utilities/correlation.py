# SPDX-License-Identifier: Apache-2.0
"""Correlation ID generation and propagation via contextvars.

Provides request-scoped correlation IDs that automatically propagate
through async call chains. The correlation ID is stored in a contextvar
so it's available to any code running within the same async context
(e.g., middleware sets it, downstream services read it).

Usage:
    1. Middleware calls set_correlation_id() at request start.
    2. Logger patcher reads get_correlation_id() to auto-bind into log records.
    3. Any code can call get_correlation_id() to include it in outgoing calls.
"""
from contextvars import ContextVar

import nanoid

correlation_id_var: ContextVar[str | None] = ContextVar(
    'correlation_id', default=None
)


def generate_correlation_id(prefix: str = 'req') -> str:
    """Generate a correlation ID in the format {prefix}_{12_char_id}.

    Uses nanoid to produce a compact, URL-safe, collision-resistant ID.

    Args:
        prefix: Short string identifying the origin context
            (e.g., 'req' for HTTP requests, 'cli' for CLI commands).

    Returns:
        A string like 'req_V1StGXR8_Z5j' (prefix + underscore + 12 chars).
    """
    return f'{prefix}_{nanoid.generate(size=12)}'


def get_correlation_id() -> str | None:
    """Read the current correlation ID from the contextvar.

    Returns:
        The correlation ID string if set in the current context,
        None otherwise.
    """
    return correlation_id_var.get(None)


def set_correlation_id(cid: str) -> None:
    """Set the correlation ID in the current async context.

    Args:
        cid: The correlation ID to store. Typically produced by
            generate_correlation_id().
    """
    correlation_id_var.set(cid)
