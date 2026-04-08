# SPDX-License-Identifier: Apache-2.0
"""Tests for LLM Client module."""

import os
import pytest
from unittest.mock import MagicMock, patch, create_autospec, Mock
from typing import Generator

import pydantic
from pydantic import SecretStr

from utilities.llm_manager.llm_client import LangChainLLMClient, LLMClient
from utilities.llm_manager.llm_schemas import LLMConfig, LLMProvider, LLMToolResponse
from utilities.llm_manager.llm_message import LLMMessage, MessageRole
from utilities.llm_manager.llm_client_user import LLMClientUser
from utilities.llm_manager.llm_factory import LLMFactory
from utilities.llm_manager.exceptions import (
    LLMConfigurationError,
    LLMProviderError,
)
from shared.config.config import backend_config


# --- Fixtures ---

@pytest.fixture
def mock_user() -> Mock:
    """Create a mock LLMClientUser."""
    user = create_autospec(LLMClientUser, instance=True, spec_set=True)
    user.get_agent_id.return_value = "test-agent"
    user.get_session_id.return_value = "test-session"
    return user


@pytest.fixture
def openai_config() -> LLMConfig:
    """Create a mock OpenAI LLM configuration for unit tests."""
    return LLMConfig(
        provider=LLMProvider.OPENAI,
        model_name="gpt-4o",
        api_key=SecretStr("mock-openai-key"),
        enable_tracing=True,
        langfuse_public_key="mock-public-key",
        langfuse_secret_key=SecretStr("mock-secret-key"),
        langfuse_host="https://mock.langfuse.com",
    )


@pytest.fixture
def azure_config() -> LLMConfig:
    """Create an Azure OpenAI LLM configuration."""
    return LLMConfig(
        provider=LLMProvider.AZURE_OPENAI,
        model_name="gpt-4",
        api_key=SecretStr("mock-azure-key"),
        api_base="https://my-resource.openai.azure.com",
        api_version="2024-02-01",
        enable_tracing=False,
    )


@pytest.fixture
def config_no_tracing() -> LLMConfig:
    """Create a mock configuration with tracing disabled."""
    return LLMConfig(
        provider=LLMProvider.OPENAI,
        model_name="gpt-4o",
        api_key=SecretStr("mock-openai-key"),
        enable_tracing=False,
    )


@pytest.fixture
def client(
    mock_user: MagicMock,
    openai_config: LLMConfig
) -> Generator[LangChainLLMClient, None, None]:
    """Create a mocked LangChainLLMClient."""
    with patch(
        "utilities.llm_manager.llm_client.ChatOpenAI"
    ) as mock_openai, patch(
        "langfuse.langchain.CallbackHandler"
    ):
        client_instance = LangChainLLMClient(mock_user, openai_config)
        # Replace with fresh MagicMock for easier assertion
        client_instance._llm = MagicMock()
        yield client_instance


# --- LLMMessage Tests ---

class TestLLMMessage:
    """Tests for LLMMessage class."""

    def test_add_system_message(self) -> None:
        """Test adding a system message."""
        # Arrange
        expected_content = "You are a helpful assistant"
        expected_role = MessageRole.SYSTEM

        # Act
        msg = LLMMessage()
        actual_result = msg.add_system_message(expected_content)

        # Assert
        assert actual_result is msg  # Fluent interface returns self
        assert len(msg.get_messages()) == 1
        assert msg.get_messages()[0]['role'] == expected_role
        assert msg.get_messages()[0]['content'] == expected_content

    def test_add_user_message(self) -> None:
        """Test adding a user message."""
        msg = LLMMessage()
        msg.add_user_message("Hello")

        assert len(msg.get_messages()) == 1
        assert msg.get_messages()[0]['role'] == MessageRole.USER
        assert msg.get_messages()[0]['content'] == "Hello"

    def test_add_assistant_message(self) -> None:
        """Test adding an assistant message."""
        msg = LLMMessage()
        msg.add_assistant_message("Hi there!")

        assert len(msg.get_messages()) == 1
        assert msg.get_messages()[0]['role'] == MessageRole.ASSISTANT
        assert msg.get_messages()[0]['content'] == "Hi there!"

    def test_add_assistant_message_with_tool_calls(self) -> None:
        """Test adding an assistant message with tool calls."""
        tool_calls = [{"id": "call_1", "function": {"name": "get_weather"}}]
        msg = LLMMessage()
        msg.add_assistant_message("", tool_calls=tool_calls)

        assert msg.get_messages()[0]['tool_calls'] == tool_calls

    def test_add_tool_message(self) -> None:
        """Test adding a tool response message."""
        msg = LLMMessage()
        msg.add_tool_message("Sunny, 72F", tool_call_id="call_1")

        assert msg.get_messages()[0]['role'] == MessageRole.TOOL
        assert msg.get_messages()[0]['content'] == "Sunny, 72F"
        assert msg.get_messages()[0]['tool_call_id'] == "call_1"

    def test_fluent_interface(self) -> None:
        """Test method chaining."""
        msg = (
            LLMMessage()
            .add_system_message("System")
            .add_user_message("User")
            .add_assistant_message("Assistant")
        )

        assert len(msg.get_messages()) == 3

    def test_to_langchain_messages(self) -> None:
        """Test conversion to LangChain message format."""
        # Arrange
        expected_system = "System prompt"
        expected_user = "Hello"
        expected_assistant = "Hi!"
        msg = (
            LLMMessage()
            .add_system_message(expected_system)
            .add_user_message(expected_user)
            .add_assistant_message(expected_assistant)
        )

        # Act
        actual_lc_messages = msg.to_langchain_messages()

        # Assert
        assert len(actual_lc_messages) == 3
        assert actual_lc_messages[0].content == expected_system
        assert actual_lc_messages[1].content == expected_user
        assert actual_lc_messages[2].content == expected_assistant

    def test_combine_messages(self) -> None:
        """Test combining two LLMMessage instances."""
        msg1 = LLMMessage().add_user_message("First")
        msg2 = LLMMessage().add_assistant_message("Second")

        combined = msg1.combine(msg2)

        assert len(combined.get_messages()) == 2
        assert len(msg1.get_messages()) == 1  # Original unchanged
        assert len(msg2.get_messages()) == 1  # Original unchanged


# --- LLMClient Tests ---

class TestLangChainLLMClientInitialization:
    """Tests for LangChainLLMClient initialization."""

    def test_openai_initialization(
        self,
        mock_user: MagicMock,
        openai_config: LLMConfig
    ) -> None:
        """Test initialization with OpenAI provider."""
        with patch(
            "utilities.llm_manager.llm_client.ChatOpenAI"
        ) as mock_openai, patch(
            "langfuse.langchain.CallbackHandler"
        ) as mock_handler:
            client = LangChainLLMClient(mock_user, openai_config)

            mock_openai.assert_called_once()
            mock_handler.assert_called_once()
            assert client._llm is not None

    def test_azure_initialization(
        self,
        mock_user: MagicMock,
        azure_config: LLMConfig
    ) -> None:
        """Test initialization with Azure OpenAI provider."""
        with patch(
            "utilities.llm_manager.llm_client.AzureChatOpenAI"
        ) as mock_azure, patch(
            "langfuse.langchain.CallbackHandler"
        ):
            client = LangChainLLMClient(mock_user, azure_config)

            mock_azure.assert_called_once()
            call_kwargs = mock_azure.call_args[1]
            assert call_kwargs['azure_endpoint'] == azure_config.api_base
            assert call_kwargs['api_version'] == azure_config.api_version

    def test_azure_missing_config_raises_error(
        self,
        mock_user: MagicMock
    ) -> None:
        """Test that Azure without api_base raises error."""
        config = LLMConfig(
            provider=LLMProvider.AZURE_OPENAI,
            model_name="gpt-4",
            api_key=SecretStr("key"),
            # Missing api_base and api_version
        )

        with pytest.raises(LLMConfigurationError) as exc_info:
            LangChainLLMClient(mock_user, config)

        assert "api_base" in str(exc_info.value)

    def test_unsupported_provider_raises_error(
        self,
        mock_user: MagicMock
    ) -> None:
        """Test that unsupported provider raises error."""
        config = LLMConfig(
            provider=LLMProvider.GROQ,  # Not yet supported
            model_name="llama-3",
            api_key=SecretStr("key"),
        )

        with pytest.raises(LLMProviderError) as exc_info:
            LangChainLLMClient(mock_user, config)

        assert "not supported" in str(exc_info.value)

    def test_tracing_disabled(
        self,
        mock_user: MagicMock,
        config_no_tracing: LLMConfig
    ) -> None:
        """Test initialization with tracing disabled."""
        with patch(
            "utilities.llm_manager.llm_client.ChatOpenAI"
        ), patch(
            "langfuse.langchain.CallbackHandler"
        ) as mock_handler:
            client = LangChainLLMClient(mock_user, config_no_tracing)

            mock_handler.assert_not_called()
            assert client._langfuse_handler is None


class TestLangChainLLMClientMethods:
    """Tests for LangChainLLMClient methods."""

    def test_call_llm(self, client: LangChainLLMClient) -> None:
        """Test synchronous LLM call."""
        msg = LLMMessage().add_user_message("Hello")

        mock_response = MagicMock()
        mock_response.content = "World"
        client._llm.invoke.return_value = mock_response

        response = client.call_llm(msg)

        assert response == "World"
        client._llm.invoke.assert_called_once()

        # Verify callbacks are passed
        _, kwargs = client._llm.invoke.call_args
        assert "callbacks" in kwargs["config"]

    def test_call_llm_structured(self, client: LangChainLLMClient) -> None:
        """Test structured output LLM call."""
        class ResponseModel(pydantic.BaseModel):
            answer: str

        msg = LLMMessage().add_user_message("Hello")
        expected_response = ResponseModel(answer="World")

        mock_raw = MagicMock()
        mock_raw.usage_metadata = {'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15}

        mock_structured_llm = MagicMock()
        mock_structured_llm.invoke.return_value = {
            'parsed': expected_response,
            'raw': mock_raw,
        }
        client._llm.with_structured_output.return_value = mock_structured_llm

        response = client.call_llm_structured(msg, ResponseModel)

        assert response == expected_response
        client._llm.with_structured_output.assert_called_once_with(ResponseModel, include_raw=True)
        mock_structured_llm.invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_acall_llm_stream(self, client: LangChainLLMClient) -> None:
        """Test async streaming LLM call."""
        msg = LLMMessage().add_user_message("Hello")

        async def mock_astream(*args, **kwargs):
            chunks = ["He", "llo", " World"]
            for c in chunks:
                chunk = MagicMock()
                chunk.content = c
                yield chunk

        client._llm.astream = mock_astream

        collected = []
        async for chunk in client.acall_llm_stream(msg):
            collected.append(chunk)

        assert "".join(collected) == "Hello World"

    def test_flush_with_handler(self, client: LangChainLLMClient) -> None:
        """Test flush method when handler exists."""
        with patch("utilities.llm_manager.llm_client.get_client") as mock_get:
            mock_langfuse = MagicMock()
            mock_get.return_value = mock_langfuse

            client.flush()

            mock_langfuse.flush.assert_called_once()

    def test_flush_without_handler(
        self,
        mock_user: MagicMock,
        config_no_tracing: LLMConfig
    ) -> None:
        """Test flush method when no handler exists."""
        with patch("utilities.llm_manager.llm_client.ChatOpenAI"):
            client = LangChainLLMClient(mock_user, config_no_tracing)

            with patch(
                "utilities.llm_manager.llm_client.get_client"
            ) as mock_get:
                client.flush()
                mock_get.assert_not_called()

    def test_get_callbacks_with_handler(
        self,
        client: LangChainLLMClient
    ) -> None:
        """Test _get_callbacks returns handler when enabled."""
        callbacks = client._get_callbacks()
        assert len(callbacks) == 1

    def test_get_callbacks_without_handler(
        self,
        mock_user: MagicMock,
        config_no_tracing: LLMConfig
    ) -> None:
        """Test _get_callbacks returns empty list when disabled."""
        with patch("utilities.llm_manager.llm_client.ChatOpenAI"):
            client = LangChainLLMClient(mock_user, config_no_tracing)

            callbacks = client._get_callbacks()
            assert callbacks == []


# --- call_llm_with_tools Tests ---

class TestCallLLMWithTools:
    """Tests for LangChainLLMClient.call_llm_with_tools."""

    def test_call_llm_with_tools_binds_and_invokes(self, client: LangChainLLMClient) -> None:
        """Test that call_llm_with_tools calls bind_tools + invoke and returns LLMToolResponse."""
        msg = LLMMessage().add_user_message("Search for python tutorials")
        tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]

        mock_bound = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "I'll search for that"
        mock_response.tool_calls = [
            {"id": "call_1", "name": "search", "args": {"query": "python tutorials"}},
        ]
        mock_bound.invoke.return_value = mock_response
        client._llm.bind_tools.return_value = mock_bound

        result = client.call_llm_with_tools(msg, tools)

        assert isinstance(result, LLMToolResponse)
        assert result.content == "I'll search for that"
        assert result.has_tool_calls is True
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "search"
        assert result.tool_calls[0]["args"] == {"query": "python tutorials"}
        client._llm.bind_tools.assert_called_once_with(tools)
        mock_bound.invoke.assert_called_once()

    def test_call_llm_with_tools_no_tool_calls(self, client: LangChainLLMClient) -> None:
        """Test call_llm_with_tools when LLM responds without tool calls."""
        msg = LLMMessage().add_user_message("Hello")
        tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]

        mock_bound = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Hi there!"
        mock_response.tool_calls = []
        mock_bound.invoke.return_value = mock_response
        client._llm.bind_tools.return_value = mock_bound

        result = client.call_llm_with_tools(msg, tools)

        assert isinstance(result, LLMToolResponse)
        assert result.content == "Hi there!"
        assert result.has_tool_calls is False
        assert result.tool_calls == []

    def test_call_llm_with_tools_records_metrics(self, client: LangChainLLMClient) -> None:
        """Test that call_llm_with_tools records metrics via _record_llm_metrics."""
        msg = LLMMessage().add_user_message("Test")
        tools = [{"type": "function", "function": {"name": "test_tool", "parameters": {}}}]

        mock_bound = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "response"
        mock_response.tool_calls = []
        mock_bound.invoke.return_value = mock_response
        client._llm.bind_tools.return_value = mock_bound

        with patch.object(client, '_record_llm_metrics') as mock_metrics:
            client.call_llm_with_tools(msg, tools)
            mock_metrics.assert_called_once()
            args = mock_metrics.call_args[0]
            assert args[0] is mock_response  # raw_response
            assert args[1] == "response"  # parsed_response (content)


# --- LLMFactory Tests ---

class TestLLMFactory:
    """Tests for LLMFactory."""

    def test_create_client(
        self,
        mock_user: MagicMock,
        openai_config: LLMConfig
    ) -> None:
        """Test factory creates LangChainLLMClient."""
        with patch(
            "utilities.llm_manager.llm_client.ChatOpenAI"
        ), patch(
            "langfuse.langchain.CallbackHandler"
        ):
            client = LLMFactory.create_client(mock_user, openai_config)

            assert isinstance(client, LLMClient)
            assert isinstance(client, LangChainLLMClient)


# --- Live Tests ---

@pytest.mark.live_llm
class TestLiveLLM:
    """
    Live tests against actual LLM providers.

    Supports both OpenAI and Azure OpenAI based on LLM_PROVIDER in config.
    Run with: pytest -m live_llm
    """

    @pytest.fixture
    def live_client(
        self,
        mock_user: MagicMock
    ) -> Generator[LangChainLLMClient, None, None]:
        """Create a live client with real API credentials."""
        api_key = backend_config.openai_api_key
        if not api_key:
            pytest.skip("openai_api_key not found in configuration")

        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model_name=backend_config.llm.model or "gpt-4o",
            api_key=SecretStr(api_key),
            api_base=None,
            api_version=None,
            enable_tracing=backend_config.langfuse_enabled,
            langfuse_public_key=backend_config.langfuse_public_key,
            langfuse_secret_key=SecretStr(
                backend_config.langfuse_secret_key or ""
            ),
            langfuse_host=backend_config.langfuse_host,
        )
        client = LangChainLLMClient(mock_user, config)
        yield client
        client.flush()

    def test_live_call_llm(self, live_client: LangChainLLMClient) -> None:
        """Test live LLM call."""
        msg = LLMMessage().add_user_message(
            "Say 'test passed' and nothing else."
        )
        response = live_client.call_llm(msg)
        assert "test passed" in response.lower()

    def test_live_call_llm_structured(
        self,
        live_client: LangChainLLMClient
    ) -> None:
        """Test live structured output call."""
        class CountryCapital(pydantic.BaseModel):
            country: str
            capital: str

        msg = LLMMessage().add_user_message(
            "What is the capital of France? Return the country and capital."
        )
        response = live_client.call_llm_structured(msg, CountryCapital)

        assert isinstance(response, CountryCapital)
        assert response.country.lower() == "france"
        assert response.capital.lower() == "paris"
