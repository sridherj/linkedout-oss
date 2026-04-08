# SPDX-License-Identifier: Apache-2.0
"""PromptManager implementation for provider-agnostic access."""

from __future__ import annotations

from typing import List, Optional

from utilities.prompt_manager.prompt_config import PromptManagerConfig
from utilities.prompt_manager.prompt_schemas import PromptSchema
from utilities.prompt_manager.prompt_store import PromptStore
from utilities.prompt_manager.local_file_store import LocalFilePromptStore
from utilities.prompt_manager.langfuse_store import LangfusePromptStore


class PromptManager:
    """
    Provider-agnostic prompt management interface.

    Provides a clean API for retrieving prompts by their stable
    internal identifier. The underlying storage is determined by
    configuration.

    HOW TO USE:
    -----------
    1. Initialize the manager (usually via factory):
       from utilities.prompt_manager import PromptFactory
       manager = PromptFactory.create_from_env()

    2. Retrieve a prompt by its key:
       # Returns a PromptSchema object
       prompt = manager.get("agents/classifier")

    3. Use with LLMManager (Recommended):
       # Bridge usage with LLMMessage
       from utilities.llm_manager import LLMMessage

       message = LLMMessage.from_prompt(
           prompt,
           variables={"context": "...", "query": "..."}
       )
       response = client.call_llm(message)

    4. Manual Compilation (Alternative):
       # For text prompts (returns str)
       compiled_text = prompt.compile(user_name="Alice")

       # For chat prompts (returns List[Dict[str, str]])
       compiled_messages = prompt.compile(
           context="You are a helpful assistant",
           query="Help me!"
       )

    Attributes:
        _config: Configuration controlling store selection and behavior.
        _store: The underlying storage implementation (local or remote).
    """

    _config: PromptManagerConfig
    _store: PromptStore

    def __init__(self, config: PromptManagerConfig) -> None:
        """
        Initialize PromptManager with configuration.

        Args:
            config: Configuration controlling store selection and behavior.
        """
        self._config = config
        self._store = _resolve_store(config)

    def get(
        self,
        prompt_key: str,
        *,
        label: Optional[str] = None,
        version: Optional[int] = None,
    ) -> PromptSchema:
        """
        Retrieve a prompt by its key.

        Args:
            prompt_key: Stable internal identifier.
            label: Optional label override.
            version: Optional specific version to retrieve.

        Returns:
            PromptSchema ready for compilation and use.
        """
        return self._store.get(
            prompt_key,
            label=label,
            version=version,
        )


def _resolve_store(config: PromptManagerConfig) -> PromptStore:
    """
    Resolve which PromptStore to use based on configuration.

    Args:
        config: PromptManager configuration.

    Returns:
        Appropriate PromptStore instance.
    """
    if config.use_local_files:
        return LocalFilePromptStore(
            prompts_directory=config.prompts_directory
        )

    return LangfusePromptStore(
        public_key=config.langfuse_public_key,
        secret_key=config.langfuse_secret_key,
        host=config.langfuse_host,
        environment=config.environment,
    )
