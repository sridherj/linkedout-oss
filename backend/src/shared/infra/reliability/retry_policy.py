# SPDX-License-Identifier: Apache-2.0
"""Config-driven retry policies using tenacity."""
from dataclasses import dataclass
from typing import Tuple, Type

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)


@dataclass
class RetryConfig:
    max_attempts: int = 3
    min_wait_seconds: float = 1.0
    max_wait_seconds: float = 60.0
    retryable_exceptions: Tuple[Type[Exception], ...] = (ConnectionError, TimeoutError)


def get_llm_retry_config() -> RetryConfig:
    """Build LLM retry config from application settings."""
    from shared.config import get_config
    cfg = get_config()
    return RetryConfig(
        max_attempts=cfg.llm.retry_max_attempts,
        min_wait_seconds=cfg.llm.retry_min_wait,
        max_wait_seconds=cfg.llm.retry_max_wait,
        retryable_exceptions=(ConnectionError, TimeoutError),
    )


def get_external_api_retry_config() -> RetryConfig:
    """Build external API retry config from application settings."""
    from shared.config import get_config
    cfg = get_config()
    return RetryConfig(
        max_attempts=cfg.external_api.retry_max_attempts,
        min_wait_seconds=1.0,
        max_wait_seconds=15.0,
        retryable_exceptions=(ConnectionError, TimeoutError),
    )


def retry_with_policy(config: RetryConfig):
    """Config-driven retry decorator using tenacity."""
    return retry(
        stop=stop_after_attempt(config.max_attempts),
        wait=wait_exponential(
            min=config.min_wait_seconds,
            max=config.max_wait_seconds,
        ),
        retry=retry_if_exception_type(config.retryable_exceptions),
        reraise=True,
    )
