# SPDX-License-Identifier: Apache-2.0
"""Unit tests for PromptSchema compilation."""

from __future__ import annotations

import pytest

from utilities.prompt_manager.exceptions import PromptCompilationError
from utilities.prompt_manager.prompt_schemas import (
    ChatMessage,
    PromptSchema,
    PromptType,
)


class TestPromptSchema:
    """Tests for PromptSchema variable extraction and compilation."""

    def test_extract_variables_text(self) -> None:
        """Test automatic variable extraction from text prompts."""
        # Arrange
        test_content = 'Hello {{name}}, your order {{order_id}} is ready.'
        expected_variables = {'name', 'order_id'}

        # Act
        actual_schema = PromptSchema(
            prompt_key='test',
            prompt_type=PromptType.TEXT,
            content=test_content,
        )

        # Assert
        assert set(actual_schema.variables) == expected_variables

    def test_extract_variables_chat(self) -> None:
        """Test automatic variable extraction from chat prompts."""
        # Arrange
        test_messages = [
            ChatMessage(role='system', content='Hello {{name}}'),
            ChatMessage(role='user', content='Order {{order_id}}'),
        ]
        expected_variables = {'name', 'order_id'}

        # Act
        actual_schema = PromptSchema(
            prompt_key='test',
            prompt_type=PromptType.CHAT,
            content=test_messages,
        )

        # Assert
        assert set(actual_schema.variables) == expected_variables

    def test_compile_text_prompt(self) -> None:
        """Test compiling a text prompt with variables."""
        # Arrange
        schema = PromptSchema(
            prompt_key='test',
            prompt_type=PromptType.TEXT,
            content='Hello {{name}}',
        )
        expected_name = 'Alice'

        # Act
        actual_compiled = schema.compile(name=expected_name)

        # Assert
        assert expected_name in actual_compiled
        assert '{{' not in actual_compiled

    def test_compile_chat_prompt(self) -> None:
        """Test compiling a chat prompt with variables."""
        # Arrange
        schema = PromptSchema(
            prompt_key='test',
            prompt_type=PromptType.CHAT,
            content=[
                ChatMessage(role='system', content='Categories: {{categories}}'),
                ChatMessage(role='user', content='Text: {{text}}'),
            ],
        )
        expected_system_content = 'Categories: A, B'
        expected_user_content = 'Text: Hello'

        # Act
        actual_compiled = schema.compile(categories='A, B', text='Hello')

        # Assert
        assert isinstance(actual_compiled, list)
        assert actual_compiled[0]['content'] == expected_system_content
        assert actual_compiled[1]['content'] == expected_user_content

    def test_compile_missing_variable_raises(self) -> None:
        """Test that missing variables raise PromptCompilationError."""
        # Arrange
        schema = PromptSchema(
            prompt_key='test',
            prompt_type=PromptType.TEXT,
            content='Hello {{name}}',
        )
        expected_missing_variable = 'name'

        # Act & Assert
        with pytest.raises(PromptCompilationError) as exc_info:
            schema.compile()

        assert expected_missing_variable in exc_info.value.missing_variables

