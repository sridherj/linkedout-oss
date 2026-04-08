# SPDX-License-Identifier: Apache-2.0
"""Langfuse guard — provides no-op stubs when Langfuse is disabled."""
from __future__ import annotations

import contextlib
import functools


def _is_enabled() -> bool:
    from shared.config.config import backend_config

    return getattr(backend_config, 'langfuse_enabled', False)


def observe(*args, **kwargs):
    """No-op @observe decorator when Langfuse is disabled."""
    if _is_enabled():
        from langfuse import observe as real_observe

        return real_observe(*args, **kwargs)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*a, **kw):
            return func(*a, **kw)

        return wrapper

    if args and callable(args[0]):
        return decorator(args[0])
    return decorator


def get_client():
    """Return Langfuse client when enabled, no-op stub when disabled."""
    if _is_enabled():
        from langfuse import get_client as real_get_client

        return real_get_client()

    return _NoOpClient()


@contextlib.contextmanager
def propagate_attributes(**kwargs):
    """No-op propagate_attributes context manager when Langfuse is disabled."""
    if _is_enabled():
        from langfuse import propagate_attributes as real_propagate

        with real_propagate(**kwargs):
            yield
    else:
        yield


class _NoOpClient:
    """No-op Langfuse client stub — silently absorbs any method chain."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def __getattr__(self, name):
        return lambda *a, **kw: self

    def start_as_current_observation(self, **kwargs):
        return self

    def flush(self):
        pass

    def trace(self, **kwargs):
        return self

    def span(self, **kwargs):
        return self

    def generation(self, **kwargs):
        return self
