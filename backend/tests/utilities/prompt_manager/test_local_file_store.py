# SPDX-License-Identifier: Apache-2.0
"""Unit tests for LocalFilePromptStore."""

from __future__ import annotations

import pytest

from utilities.prompt_manager.exceptions import PromptNotFoundError
from utilities.prompt_manager.local_file_store import LocalFilePromptStore
from utilities.prompt_manager.prompt_schemas import PromptType


class TestLocalFilePromptStore:
    """Tests for LocalFilePromptStore using real prompt files."""

    @pytest.fixture(scope='class')
    def store(self) -> LocalFilePromptStore:
        """
        LocalFilePromptStore pointing to test prompts.

        Returns:
            LocalFilePromptStore instance.
        """
        return LocalFilePromptStore(prompts_directory='prompts')

    def test_get_text_prompt(self, store: LocalFilePromptStore) -> None:
        """Test loading a text prompt from local files."""
        # Arrange
        expected_key = 'test/simple/greeting'
        expected_type = PromptType.TEXT
        expected_variable = '{{name}}'

        # Act
        actual_prompt = store.get(expected_key)

        # Assert
        assert actual_prompt.prompt_key == expected_key
        assert actual_prompt.prompt_type == expected_type
        assert expected_variable in actual_prompt.content

    def test_get_chat_prompt(self, store: LocalFilePromptStore) -> None:
        """Test loading a chat prompt from local files."""
        # Arrange
        expected_key = 'test/chat/classifier'
        expected_type = PromptType.CHAT
        expected_message_count = 2
        expected_first_role = 'system'

        # Act
        actual_prompt = store.get(expected_key)

        # Assert
        assert actual_prompt.prompt_key == expected_key
        assert actual_prompt.prompt_type == expected_type
        assert len(actual_prompt.content) == expected_message_count
        assert actual_prompt.content[0].role == expected_first_role

    def test_get_prompt_with_label(self, store: LocalFilePromptStore) -> None:
        """Test fetching a prompt with a valid label."""
        # Arrange
        expected_key = 'test/chat/classifier'
        expected_label = 'staging'

        # Act
        actual_prompt = store.get(expected_key, label=expected_label)

        # Assert
        assert actual_prompt.prompt_key == expected_key
        assert expected_label in actual_prompt.labels

    def test_get_prompt_with_invalid_label_raises(
        self,
        store: LocalFilePromptStore,
    ) -> None:
        """Test that fetching with an invalid label raises PromptNotFoundError."""
        # Arrange
        test_key = 'test/chat/classifier'
        invalid_label = 'nonexistent'
        expected_error_message = f"Label '{invalid_label}' not found"

        # Act & Assert
        with pytest.raises(PromptNotFoundError) as exc_info:
            store.get(test_key, label=invalid_label)

        assert expected_error_message in str(exc_info.value)

