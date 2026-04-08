# SPDX-License-Identifier: Apache-2.0
"""LLM Client implementations for interacting with language models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterable, Optional, Type, List
import os
import time

import pydantic
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_core.language_models import BaseChatModel
from shared.utilities.langfuse_guard import get_client

from utilities.llm_manager.llm_client_user import LLMClientUser
from utilities.llm_manager.llm_schemas import LLMConfig, LLMProvider, LLMToolResponse
from utilities.llm_manager.llm_message import LLMMessage
from utilities.llm_manager.exceptions import (
    LLMConfigurationError,
    LLMProviderError
)
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")


class LLMClient(ABC):
    """
    Abstract base class for LLM Clients.

    Provides a unified interface for interacting with language models,
    supporting synchronous calls, structured output, and streaming.

    HOW TO USE:
    -----------
    1. Initialize the client using a factory or directly with a user and config:
       client = LLMFactory.create_client(user, config)

    2. Create an LLMMessage object and add messages:
       msg = LLMMessage()
       msg.add_system_message("You are...").add_user_message("Hello")

    3. Call the LLM:
       response_text = client.call_llm(msg)

    4. Call with Structured Output:
       class Response(BaseModel):
           answer: str
           confidence: float

       response_obj = client.call_llm_structured(msg, Response)

    5. Stream the response:
       async for chunk in client.acall_llm_stream(msg):
           print(chunk)

    Attributes:
        _user: The user/agent context for tracking.
        _config: The LLM configuration settings.
    """

    def __init__(self, user: LLMClientUser, config: LLMConfig):
        """
        Initialize the LLM client.

        Args:
            user: The user/agent context providing identity for tracking.
            config: Configuration settings for the LLM provider.
        """
        self._user: LLMClientUser = user
        self._config: LLMConfig = config

    @abstractmethod
    def call_llm(self, message: LLMMessage) -> str:
        """
        Make a synchronous call to the LLM.

        Args:
            message: The LLMMessage containing the conversation history.

        Returns:
            The text content of the LLM's response.

        Raises:
            LLMProviderError: If the LLM call fails.
        """
        pass

    @abstractmethod
    def call_llm_with_tools(self, message: LLMMessage, tools: list[dict]) -> LLMToolResponse:
        """Make a synchronous call to the LLM with tool definitions bound."""
        pass

    @abstractmethod
    def call_llm_structured(
        self,
        message: LLMMessage,
        response_model: Type[pydantic.BaseModel]
    ) -> pydantic.BaseModel:
        """
        Make a synchronous call expecting structured output.

        Args:
            message: The LLMMessage containing the conversation history.
            response_model: A Pydantic model class defining the expected
                response structure.

        Returns:
            An instance of response_model populated with the LLM's response.

        Raises:
            LLMProviderError: If the LLM call fails.
            LLMParsingError: If the response cannot be parsed into the model.
        """
        pass

    @abstractmethod
    async def acall_llm_stream(
        self,
        message: LLMMessage
    ) -> AsyncIterable[str]:
        """
        Make an asynchronous streaming call to the LLM.

        Args:
            message: The LLMMessage containing the conversation history.

        Yields:
            String chunks of the LLM's response as they arrive.

        Raises:
            LLMProviderError: If the LLM call fails.
        """
        pass


class LangChainLLMClient(LLMClient):
    """
    LLM Client implementation using LangChain and Langfuse.

    Uses LangChain for provider abstraction and Langfuse for tracing
    and observability. Supports OpenAI and Azure OpenAI providers.

    Attributes:
        _llm: The underlying LangChain chat model.
        _langfuse_handler: Optional Langfuse callback handler for tracing.
        _original_env: Backup of original environment variables.
    """

    def __init__(self, user: LLMClientUser, config: LLMConfig):
        """
        Initialize the LangChain LLM client.

        Args:
            user: The user/agent context providing identity for tracking.
            config: Configuration settings for the LLM provider.

        Raises:
            LLMConfigurationError: If required configuration is missing.
            LLMProviderError: If the provider is not supported.
        """
        super().__init__(user, config)
        self._original_env: dict[str, Optional[str]] = {}
        self._llm: BaseChatModel = self._create_langchain_client()
        self._langfuse_handler = self._create_langfuse_handler()

    def _create_langchain_client(self) -> BaseChatModel:
        """
        Create the underlying LangChain client based on provider.

        Returns:
            A configured LangChain chat model instance.

        Raises:
            LLMConfigurationError: If Azure config is incomplete.
            LLMProviderError: If the provider is not supported.
        """
        params: dict = {
            'model': self._config.model_name,
            'temperature': self._config.temperature,
            'max_tokens': self._config.max_tokens,
            'max_retries': self._config.max_retries,
            'timeout': self._config.timeout,
        }

        if self._config.api_key:
            params['api_key'] = self._config.api_key.get_secret_value()

        if self._config.provider == LLMProvider.AZURE_OPENAI:
            if not self._config.api_base or not self._config.api_version:
                raise LLMConfigurationError(
                    "Azure OpenAI requires api_base and api_version"
                )
            params['azure_endpoint'] = self._config.api_base
            params['api_version'] = self._config.api_version
            return AzureChatOpenAI(**params)

        if self._config.provider == LLMProvider.OPENAI:
            return ChatOpenAI(**params)

        raise LLMProviderError(
            f"Provider {self._config.provider} not supported "
            "in LangChainLLMClient yet."
        )

    def _create_langfuse_handler(self):
        """
        Initialize the Langfuse callback handler for tracing.

        Configures environment variables for Langfuse SDK and creates
        a callback handler. Backs up original env vars for cleanup.

        Returns:
            A configured CallbackHandler, or None if tracing is disabled
            or credentials are missing.
        """
        if not self._config.enable_tracing:
            logger.debug("Langfuse tracing disabled via config")
            return None

        # Get credentials from config or settings
        from shared.config import get_config

        settings = get_config()
        public_key = (
            self._config.langfuse_public_key
            or settings.langfuse_public_key
        )
        secret_key = self._config.langfuse_secret_key
        secret_key_value = (
            secret_key.get_secret_value()
            if secret_key
            else settings.langfuse_secret_key
        )
        host = (
            self._config.langfuse_host
            or settings.langfuse_host
        )

        if not public_key or not secret_key_value:
            logger.warning(
                "Langfuse keys not found in config or environment. "
                "Tracing disabled."
            )
            return None

        # Backup original env vars before modifying
        self._original_env = {
            "LANGFUSE_PUBLIC_KEY": os.environ.get("LANGFUSE_PUBLIC_KEY"),
            "LANGFUSE_SECRET_KEY": os.environ.get("LANGFUSE_SECRET_KEY"),
            "LANGFUSE_HOST": os.environ.get("LANGFUSE_HOST"),
        }

        # Set environment variables for Langfuse SDK
        os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
        os.environ["LANGFUSE_SECRET_KEY"] = secret_key_value
        if host:
            os.environ["LANGFUSE_HOST"] = host

        logger.info(
            f"Langfuse tracing enabled. "
            f"Host: {host or 'default (cloud.langfuse.com)'}"
        )

        from langfuse.langchain import CallbackHandler

        return CallbackHandler()

    def _get_callbacks(self) -> list:
        """
        Get the list of callbacks to use for LLM calls.

        Returns:
            List containing the Langfuse handler if enabled, empty otherwise.
        """
        if self._langfuse_handler:
            return [self._langfuse_handler]
        return []

    def flush(self) -> None:
        """
        Flush Langfuse traces to ensure they are sent.

        Should be called before process exits to ensure all traces
        are transmitted to Langfuse.
        """
        if not self._langfuse_handler:
            return

        try:
            langfuse_client = get_client()
            langfuse_client.flush()
            logger.debug("Langfuse traces flushed successfully")
        except Exception as e:
            logger.warning(f"Failed to flush Langfuse traces: {e}")

    def _record_llm_metrics(
        self, raw_response, parsed_response, latency_ms: float
    ) -> None:
        """Extract token usage from LangChain response and record metrics via callback."""
        tokens = {}
        if hasattr(raw_response, 'usage_metadata') and raw_response.usage_metadata:
            tokens = raw_response.usage_metadata
        elif hasattr(raw_response, 'response_metadata'):
            token_usage = raw_response.response_metadata.get('token_usage', {})
            tokens = {
                'input_tokens': token_usage.get('prompt_tokens', 0),
                'output_tokens': token_usage.get('completion_tokens', 0),
                'total_tokens': token_usage.get('total_tokens', 0),
            }

        llm_output = (
            parsed_response.model_dump(mode='json')
            if hasattr(parsed_response, 'model_dump')
            else str(parsed_response)
        )

        self._user.record_llm_cost(cost_usd=0, metadata={
            'latency_ms': latency_ms,
            'model': self._config.model_name,
            'input_tokens': tokens.get('input_tokens', 0),
            'output_tokens': tokens.get('output_tokens', 0),
            'total_tokens': tokens.get('total_tokens', 0),
            'llm_output': llm_output,
        })

    def call_llm(self, message: LLMMessage) -> str:
        """
        Make a synchronous call to the LLM.

        Args:
            message: The LLMMessage containing the conversation history.

        Returns:
            The text content of the LLM's response.

        Raises:
            LLMProviderError: If the LLM call fails.
        """
        lc_messages = message.to_langchain_messages()
        start_ns = time.perf_counter_ns()
        response = self._llm.invoke(
            lc_messages,
            config={'callbacks': self._get_callbacks()}
        )
        latency_ms = round((time.perf_counter_ns() - start_ns) / 1_000_000, 2)
        self._record_llm_metrics(response, response.content, latency_ms)
        return str(response.content)

    def call_llm_with_tools(self, message: LLMMessage, tools: list[dict]) -> LLMToolResponse:
        """Make a synchronous call to the LLM with tool definitions bound."""
        lc_messages = message.to_langchain_messages()
        tools_llm = self._llm.bind_tools(tools)

        start_ns = time.perf_counter_ns()
        response = tools_llm.invoke(
            lc_messages,
            config={'callbacks': self._get_callbacks()}
        )
        latency_ms = round((time.perf_counter_ns() - start_ns) / 1_000_000, 2)
        self._record_llm_metrics(response, response.content, latency_ms)

        tool_calls = []
        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tc in response.tool_calls:
                tool_calls.append({
                    "id": tc.get("id", ""),
                    "name": tc.get("name", ""),
                    "args": tc.get("args", {}),
                })

        return LLMToolResponse(
            content=str(response.content),
            tool_calls=tool_calls,
        )

    def call_llm_structured(
        self,
        message: LLMMessage,
        response_model: Type[pydantic.BaseModel]
    ) -> pydantic.BaseModel:
        """
        Make a synchronous call expecting structured output.

        Args:
            message: The LLMMessage containing the conversation history.
            response_model: A Pydantic model class defining the expected
                response structure.

        Returns:
            An instance of response_model populated with the LLM's response.

        Raises:
            LLMProviderError: If the LLM call fails.
            LLMParsingError: If the response cannot be parsed into the model.
        """
        lc_messages = message.to_langchain_messages()
        structured_llm = self._llm.with_structured_output(
            response_model, include_raw=True
        )

        start_ns = time.perf_counter_ns()
        response = structured_llm.invoke(
            lc_messages,
            config={'callbacks': self._get_callbacks()}
        )
        latency_ms = round((time.perf_counter_ns() - start_ns) / 1_000_000, 2)

        # Extract raw and parsed responses for metrics
        raw = response.get('raw') if isinstance(response, dict) else response
        parsed = response.get('parsed') if isinstance(response, dict) else response
        self._record_llm_metrics(raw, parsed, latency_ms)

        if isinstance(response, dict):
            return response['parsed']  # type: ignore[return-value]
        return response  # type: ignore[return-value]

    async def acall_llm_stream(
        self,
        message: LLMMessage
    ) -> AsyncIterable[str]:
        """
        Make an asynchronous streaming call to the LLM.

        Args:
            message: The LLMMessage containing the conversation history.

        Yields:
            String chunks of the LLM's response as they arrive.

        Raises:
            LLMProviderError: If the LLM call fails.
        """
        lc_messages = message.to_langchain_messages()

        async for chunk in self._llm.astream(
            lc_messages,
            config={'callbacks': self._get_callbacks()}
        ):
            yield str(chunk.content)
