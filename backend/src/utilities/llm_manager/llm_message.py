# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import copy
from typing import List, Dict, Optional, Any
from enum import StrEnum

from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    BaseMessage
)

from utilities.llm_manager.llm_schemas import LLMMessageMetadata
from utilities.prompt_manager.prompt_schemas import PromptSchema, PromptType


class MessageRole(StrEnum):
    """Enum representing different roles in a chat conversation."""

    SYSTEM = 'system'
    USER = 'user'
    ASSISTANT = 'assistant'
    TOOL = 'tool'


class LLMMessage:
    """
    Manage chat messages for LLM interactions.

    This class provides a fluent interface for building conversation
    histories that can be converted to LangChain message format. It is
    provider-agnostic and does not depend on specific agent schemas.

    Attributes:
        _messages: Internal list of message dictionaries.
        _metadata: Optional metadata for tracing and logging.
    """

    def __init__(self, metadata: Optional[LLMMessageMetadata] = None):
        """
        Initialize a new LLMMessage instance.

        Args:
            metadata: Optional metadata for request tracing and logging.
        """
        self._messages: List[Dict[str, Any]] = []
        self._metadata: Optional[LLMMessageMetadata] = metadata

    def add_system_message(self, content: str) -> LLMMessage:
        """
        Add a system message to the conversation.

        Args:
            content: The system prompt or instruction text.

        Returns:
            Self for method chaining.
        """
        self._messages.append({
            'role': MessageRole.SYSTEM,
            'content': content
        })
        return self

    def add_user_message(self, content: str) -> LLMMessage:
        """
        Add a user message to the conversation.

        Args:
            content: The user's message text.

        Returns:
            Self for method chaining.
        """
        self._messages.append({
            'role': MessageRole.USER,
            'content': content
        })
        return self

    def add_assistant_message(
        self,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> LLMMessage:
        """
        Add an assistant message to the conversation.

        Args:
            content: The assistant's response text.
            tool_calls: Optional list of tool call dictionaries if the
                assistant is invoking tools.

        Returns:
            Self for method chaining.
        """
        msg: Dict[str, Any] = {
            'role': MessageRole.ASSISTANT,
            'content': content
        }
        if tool_calls:
            msg['tool_calls'] = tool_calls
        self._messages.append(msg)
        return self

    def add_tool_message(self, content: str, tool_call_id: str) -> LLMMessage:
        """
        Add a tool response message to the conversation.

        Args:
            content: The tool's response content.
            tool_call_id: The ID of the tool call this responds to.

        Returns:
            Self for method chaining.
        """
        self._messages.append({
            'role': MessageRole.TOOL,
            'content': content,
            'tool_call_id': tool_call_id
        })
        return self

    def to_langchain_messages(self) -> List[BaseMessage]:
        """
        Convert internal messages to LangChain message format.

        Returns:
            List of LangChain BaseMessage objects suitable for passing
            to LangChain chat models.
        """
        lc_messages: List[BaseMessage] = []

        for msg in self._messages:
            role = msg['role']
            content = msg.get('content') or ''

            if role == MessageRole.SYSTEM:
                lc_messages.append(SystemMessage(content=content))
            elif role == MessageRole.USER:
                lc_messages.append(HumanMessage(content=content))
            elif role == MessageRole.ASSISTANT:
                tool_calls = msg.get('tool_calls')
                if tool_calls:
                    lc_messages.append(
                        AIMessage(content=content, tool_calls=tool_calls)
                    )
                else:
                    lc_messages.append(AIMessage(content=content))
            elif role == MessageRole.TOOL:
                tool_call_id = msg.get('tool_call_id')
                lc_messages.append(
                    ToolMessage(content=content, tool_call_id=tool_call_id)
                )

        return lc_messages

    def combine(self, other: LLMMessage) -> LLMMessage:
        """
        Combine this message with another LLMMessage.

        Creates a new LLMMessage containing all messages from this instance
        followed by all messages from the other instance.

        Args:
            other: Another LLMMessage to append.

        Returns:
            A new LLMMessage containing the combined messages.
        """
        new_msg = copy.deepcopy(self)
        new_msg._messages.extend(other._messages)
        return new_msg

    def get_messages(self) -> List[Dict[str, Any]]:
        """
        Get the raw message list.

        Returns:
            List of message dictionaries with 'role' and 'content' keys.
        """
        return self._messages

    @classmethod
    def from_prompt(
        cls,
        prompt: PromptSchema,
        variables: Optional[Dict[str, Any]] = None,
        metadata: Optional[LLMMessageMetadata] = None,
    ) -> LLMMessage:
        """
        Create an LLMMessage from a compiled prompt.

        Text prompts are loaded as a single system message. Chat
        prompts are loaded as a sequence of messages with their roles
        preserved.

        Args:
            prompt: PromptSchema instance from PromptManager.
            variables: Template variable values for compilation.
            metadata: Optional metadata for tracing and logging.

        Returns:
            New LLMMessage instance populated with prompt messages.

        Raises:
            PromptCompilationError: If required variables are missing.
        """
        instance = cls(metadata=metadata)
        variables = variables or {}
        compiled = prompt.compile(**variables)

        if prompt.prompt_type == PromptType.TEXT:
            instance.add_system_message(compiled)
            return instance

        for msg in compiled:
            role = msg.get('role')
            content = msg.get('content')
            if role == MessageRole.SYSTEM:
                instance.add_system_message(content)
            elif role == MessageRole.USER:
                instance.add_user_message(content)
            elif role == MessageRole.ASSISTANT:
                instance.add_assistant_message(content)
            elif role == MessageRole.TOOL:
                tool_call_id = msg.get('tool_call_id', '')
                instance.add_tool_message(content, tool_call_id)

        return instance
