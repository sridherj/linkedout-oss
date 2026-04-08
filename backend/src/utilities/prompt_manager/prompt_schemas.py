# SPDX-License-Identifier: Apache-2.0
"""Pydantic schemas for prompt management."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from utilities.prompt_manager.exceptions import PromptCompilationError

_VARIABLE_PATTERN = re.compile(r'{{\s*([a-zA-Z0-9_]+)\s*}}')


class PromptType(StrEnum):
    """
    Type of prompt content.

    Attributes:
        TEXT: Single string prompt content.
        CHAT: List of role-based messages.
    """

    TEXT = 'text'
    CHAT = 'chat'


class ChatMessage(BaseModel):
    """
    Single message in a chat prompt.

    Attributes:
        role: Message role (system, user, assistant, tool).
        content: Message content.
    """

    model_config = ConfigDict(from_attributes=True)

    role: Annotated[str, Field(description='Message role')]
    content: Annotated[str, Field(description='Message content')]


class PromptSchema(BaseModel):
    """
    Provider-agnostic prompt representation.

    This is the canonical object returned by PromptManager.get(). It
    contains the prompt content, metadata, and optional configuration.
    """

    model_config = ConfigDict(from_attributes=True)

    prompt_key: Annotated[
        str,
        Field(description='Stable internal identifier'),
    ]
    prompt_type: Annotated[
        PromptType,
        Field(description='Text or chat prompt'),
    ]
    content: Annotated[
        Union[str, List[ChatMessage]],
        Field(description='Prompt content - string or message list'),
    ]
    version: Annotated[
        Optional[int],
        Field(default=None, description='Version number'),
    ]
    labels: Annotated[
        List[str],
        Field(default_factory=list, description='Assigned labels'),
    ]
    config: Annotated[
        Optional[Dict[str, Any]],
        Field(default=None, description='Model config'),
    ]
    variables: Annotated[
        List[str],
        Field(default_factory=list, description='Template variables'),
    ]

    def model_post_init(self, __context: Any) -> None:
        """
        Extract template variables after initialization.

        Args:
            __context: Pydantic context (unused).
        """
        extracted = self._extract_variables()
        self.variables = sorted(set(extracted))

    def compile(self, **kwargs: str) -> Union[str, List[Dict[str, str]]]:
        """
        Replace template variables with provided values.

        Variables use double-brace syntax: ``{{variable_name}}``. This method
        substitutes all variables with the provided keyword arguments.

        Example - Text Prompt::

            >>> schema = PromptSchema(
            ...     prompt_key='greeting',
            ...     prompt_type=PromptType.TEXT,
            ...     content='Hello {{name}}, your order {{order_id}} is ready.',
            ... )
            >>> schema.compile(name='Alice', order_id='12345')
            'Hello Alice, your order 12345 is ready.'

        Example - Chat Prompt::

            >>> schema = PromptSchema(
            ...     prompt_key='classifier',
            ...     prompt_type=PromptType.CHAT,
            ...     content=[
            ...         ChatMessage(role='system', content='Classify: {{categories}}'),
            ...         ChatMessage(role='user', content='Text: {{text}}'),
            ...     ],
            ... )
            >>> schema.compile(categories='A, B, C', text='Hello world')
            [
                {'role': 'system', 'content': 'Classify: A, B, C'},
                {'role': 'user', 'content': 'Text: Hello world'},
            ]

        Args:
            **kwargs: Variable name to value mappings. All variables found
                in the prompt content must be provided.

        Returns:
            Compiled prompt - string for text prompts, list of message dicts
            for chat prompts.

        Raises:
            PromptCompilationError: If a required variable is not provided.
        """
        missing_variables = [
            variable for variable in self.variables if variable not in kwargs
        ]
        if missing_variables:
            raise PromptCompilationError(self.prompt_key, missing_variables)

        if self.prompt_type == PromptType.TEXT:
            return self._compile_text(self.content, kwargs)

        messages: List[Dict[str, str]] = []
        for msg in self.content:
            compiled_content = self._compile_text(msg.content, kwargs)
            messages.append({'role': msg.role, 'content': compiled_content})
        return messages

    def _extract_variables(self) -> List[str]:
        """
        Extract variables from prompt content.

        Returns:
            List of variable names found in the prompt.
        """
        variables: List[str] = []
        if self.prompt_type == PromptType.TEXT:
            variables.extend(_VARIABLE_PATTERN.findall(self.content))
            return variables

        for msg in self.content:
            variables.extend(_VARIABLE_PATTERN.findall(msg.content))
        return variables

    def _compile_text(self, text: str, variables: Dict[str, str]) -> str:
        """
        Compile a text template with provided variables.

        Args:
            text: Template text with variable placeholders.
            variables: Variable values to substitute.

        Returns:
            Compiled string with variables substituted.
        """
        def replace(match: re.Match) -> str:
            variable_name = match.group(1)
            return str(variables[variable_name])

        return _VARIABLE_PATTERN.sub(replace, text)


class PromptMetadata(BaseModel):
    """
    Metadata stored alongside local prompt files.

    This metadata is persisted in <prompt_key>.meta.jsonc files and
    tracks the relationship between local files and remote provider
    state.
    """

    model_config = ConfigDict(from_attributes=True)

    prompt_key: Annotated[
        str,
        Field(description='Stable internal identifier'),
    ]
    prompt_type: Annotated[
        PromptType,
        Field(default=PromptType.TEXT),
    ]
    content_file: Annotated[
        str,
        Field(description='Relative path to content file'),
    ]
    version: Annotated[
        Optional[str],
        Field(default=None, description='Local version'),
    ]
    labels: Annotated[
        List[str],
        Field(default_factory=list, description='Assigned labels'),
    ]
    config: Annotated[Optional[Dict[str, Any]], Field(default=None)]

