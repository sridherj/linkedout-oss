# SPDX-License-Identifier: Apache-2.0
"""
LLM Manager - A unified interface for LLM interactions.

This module provides a clean abstraction for interacting with various
LLM providers (OpenAI, Azure OpenAI, etc.) with built-in support for
tracing via Langfuse.

Example:
    from utilities.llm_manager import (
        LLMFactory, LLMConfig, LLMProvider, LLMMessage
    )

    from shared.config import get_config
    settings = get_config()
    config = LLMConfig(
        provider=LLMProvider.OPENAI,
        model_name="gpt-4",
        api_key=SecretStr(settings.openai_api_key),
    )

    client = LLMFactory.create_client(user, config)
    msg = LLMMessage().add_user_message("Hello!")
    response = client.call_llm(msg)
"""

from utilities.llm_manager.llm_schemas import (
    LLMConfig,
    LLMProvider,
    LLMMessageMetadata,
    LLMMetrics,
    LLMToolResponse,
)
from utilities.llm_manager.llm_message import LLMMessage, MessageRole
from utilities.llm_manager.llm_client_user import LLMClientUser, SystemUser
from utilities.llm_manager.llm_client import LLMClient, LangChainLLMClient
from utilities.llm_manager.llm_factory import LLMFactory
from utilities.llm_manager.embedding_client import EmbeddingClient
from utilities.llm_manager.embedding_provider import EmbeddingProvider
from utilities.llm_manager.embedding_factory import get_embedding_provider, get_embedding_column_name
from utilities.llm_manager.openai_embedding_provider import OpenAIEmbeddingProvider
from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider
from utilities.llm_manager.conversation_manager import ConversationManager, SummaryResult
from utilities.llm_manager.exceptions import (
    LLMError,
    LLMConfigurationError,
    LLMProviderError,
    LLMParsingError,
)

__all__ = [
    # Configuration
    'LLMConfig',
    'LLMProvider',
    'LLMMessageMetadata',
    'LLMMetrics',
    'LLMToolResponse',
    # Messages
    'LLMMessage',
    'MessageRole',
    # Client Interface
    'LLMClientUser',
    'SystemUser',
    'LLMClient',
    'LangChainLLMClient',
    # Factory
    'LLMFactory',
    # Embedding
    'EmbeddingClient',
    'EmbeddingProvider',
    'get_embedding_provider',
    'get_embedding_column_name',
    'OpenAIEmbeddingProvider',
    'LocalEmbeddingProvider',
    # Conversation
    'ConversationManager',
    'SummaryResult',
    # Exceptions
    'LLMError',
    'LLMConfigurationError',
    'LLMProviderError',
    'LLMParsingError',
]
