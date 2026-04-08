# SPDX-License-Identifier: Apache-2.0
"""Config-driven timeout policies."""
import signal
from dataclasses import dataclass
from functools import wraps


@dataclass
class TimeoutConfig:
    timeout_seconds: float = 30.0


def get_llm_timeout_config() -> TimeoutConfig:
    """Build LLM timeout config from application settings."""
    from shared.config import get_config
    return TimeoutConfig(timeout_seconds=get_config().llm.timeout_seconds)


def get_external_api_timeout_config() -> TimeoutConfig:
    """Build external API timeout config from application settings."""
    from shared.config import get_config
    return TimeoutConfig(timeout_seconds=get_config().external_api.timeout_seconds)


class TimeoutError(Exception):
    """Raised when an operation exceeds its configured timeout."""


def timeout_with_policy(config: TimeoutConfig):
    """Signal-based timeout decorator (Unix main thread only).

    Falls back to no-op on platforms without signal.SIGALRM or when
    called from non-main threads.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Only use signal-based timeout on Unix in main thread
            if not hasattr(signal, 'SIGALRM'):
                return func(*args, **kwargs)

            import threading
            if threading.current_thread() is not threading.main_thread():
                return func(*args, **kwargs)

            def handler(signum, frame):
                raise TimeoutError(
                    f'{func.__name__} timed out after {config.timeout_seconds}s'
                )

            old_handler = signal.signal(signal.SIGALRM, handler)
            signal.alarm(int(config.timeout_seconds))
            try:
                return func(*args, **kwargs)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

        return wrapper
    return decorator
