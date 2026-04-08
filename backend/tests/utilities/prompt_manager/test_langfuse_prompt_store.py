# SPDX-License-Identifier: Apache-2.0
"""Integration tests for Langfuse prompt stores."""

from __future__ import annotations

import os

import pytest
from pydantic import SecretStr

from utilities.prompt_manager.langfuse_store import (
    LangfusePromptStore,
    LangfusePromptStoreTooling,
)
from utilities.prompt_manager.exceptions import PromptNotFoundError
from utilities.prompt_manager.prompt_schemas import (
    PromptSchema,
    PromptType,
)
from shared.config.config import backend_config


@pytest.mark.live_langfuse
class TestLangfusePromptStore:
    """Integration tests using real Langfuse API calls."""

    @pytest.fixture(scope='class')
    def store(self) -> LangfusePromptStore:
        """
        LangfusePromptStore configured from environment.

        Returns:
            LangfusePromptStore instance.
        """
        if not backend_config.langfuse_public_key:
            pytest.skip("langfuse_public_key not configured")

        return LangfusePromptStore(
            public_key=SecretStr(backend_config.langfuse_public_key),
            secret_key=SecretStr(backend_config.langfuse_secret_key or ""),
            host=backend_config.langfuse_host,
            environment='test',
        )

    @pytest.fixture(scope='class')
    def tooling(self) -> LangfusePromptStoreTooling:
        """
        LangfusePromptStoreTooling configured from environment.

        Returns:
            LangfusePromptStoreTooling instance.
        """
        return LangfusePromptStoreTooling(
            public_key=SecretStr(backend_config.langfuse_public_key or ""),
            secret_key=SecretStr(backend_config.langfuse_secret_key or ""),
            host=backend_config.langfuse_host,
        )

    def test_push_and_get_prompt(
        self,
        store: LangfusePromptStore,
        tooling: LangfusePromptStoreTooling,
    ) -> None:
        """
        Test pushing a prompt to Langfuse and retrieving it.
        """
        test_prompt = PromptSchema(
            prompt_key='test/integration/simple',
            prompt_type=PromptType.TEXT,
            content='Hello {{name}}!',
        )

        pushed = tooling.push(test_prompt, labels=['test'])
        assert pushed.version is not None

        retrieved = store.get('test/integration/simple', label='test')
        assert retrieved.content == test_prompt.content

    def test_get_nonexistent_prompt_raises(
        self,
        store: LangfusePromptStore,
    ) -> None:
        """
        Test that getting a nonexistent prompt raises error.
        """
        with pytest.raises(PromptNotFoundError):
            store.get('nonexistent/prompt/key', label='test')
