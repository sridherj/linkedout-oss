# SPDX-License-Identifier: Apache-2.0
"""Factory for creating LLM clients."""

from __future__ import annotations

from utilities.llm_manager.llm_schemas import LLMConfig
from utilities.llm_manager.llm_client_user import LLMClientUser
from utilities.llm_manager.llm_client import LLMClient, LangChainLLMClient


class LLMFactory:
    """
    Factory for creating LLM Client instances.

    Provides a centralized way to create LLM clients based on configuration.
    The factory pattern allows for easy extension to support additional
    client implementations in the future.

    Example:
        config = LLMConfig(provider=LLMProvider.OPENAI, model_name="gpt-4")
        client = LLMFactory.create_client(user, config)
    """

    @staticmethod
    def create_client(user: LLMClientUser, config: LLMConfig) -> LLMClient:
        """
        Create an LLMClient based on the configuration.

        Currently creates a LangChainLLMClient for all supported providers.
        Future implementations may return different client types based on
        provider or other configuration options.

        Args:
            user: The user/agent context providing identity for tracking.
            config: Configuration settings for the LLM provider.

        Returns:
            An initialized LLMClient ready for use.

        Raises:
            LLMConfigurationError: If required configuration is missing.
            LLMProviderError: If the provider is not supported.
        """
        # Future: Add logic to select different client implementations
        # based on provider or config flags
        return LangChainLLMClient(user, config)
