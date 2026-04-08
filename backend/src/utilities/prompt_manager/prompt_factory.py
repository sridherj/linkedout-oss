# SPDX-License-Identifier: Apache-2.0
"""Factory for creating PromptManager instances."""

from __future__ import annotations

from pydantic import SecretStr

from utilities.prompt_manager.prompt_config import PromptManagerConfig
from utilities.prompt_manager.prompt_manager import PromptManager


class PromptFactory:
    """
    Factory for creating PromptManager instances.

    Provides a centralized way to create PromptManager with proper
    configuration from environment variables or explicit config.
    """

    @staticmethod
    def create(config: PromptManagerConfig) -> PromptManager:
        """
        Create PromptManager with explicit configuration.

        Args:
            config: PromptManager configuration.

        Returns:
            Configured PromptManager instance.
        """
        return PromptManager(config)

    @staticmethod
    def create_from_env() -> PromptManager:
        """
        Create PromptManager from environment variables.

        Returns:
            PromptManager configured from environment variables.
        """
        from shared.config import get_config

        settings = get_config()
        config = PromptManagerConfig(
            use_local_files=settings.prompt_from_local_file,
            prompts_directory=settings.prompts_directory,
            environment=settings.environment,
            cache_ttl_seconds=settings.llm.prompt_cache_ttl_seconds,
            langfuse_public_key=(
                SecretStr(settings.langfuse_public_key)
                if settings.langfuse_public_key
                else None
            ),
            langfuse_secret_key=(
                SecretStr(settings.langfuse_secret_key)
                if settings.langfuse_secret_key
                else None
            ),
            langfuse_host=settings.langfuse_host,
        )
        return PromptFactory.create(config)
