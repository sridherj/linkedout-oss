# SPDX-License-Identifier: Apache-2.0
"""Custom exceptions for the Prompt Manager module."""

from __future__ import annotations

from typing import List, Optional


class PromptError(Exception):
    """
    Base exception for all prompt-related errors.

    All prompt management exceptions inherit from this class, allowing
    callers to catch all prompt errors with a single except clause.
    """


class PromptNotFoundError(PromptError):
    """
    Error raised when a prompt cannot be found.

    This is raised when a prompt key does not exist or when label filtering
    results in no matching prompt.
    """

    def __init__(
        self,
        prompt_key: str,
        label: Optional[str] = None,
    ) -> None:
        """
        Initialize the exception with prompt context.

        Args:
            prompt_key: Prompt key that could not be resolved.
            label: Optional label used in retrieval.
        """
        self.prompt_key = prompt_key
        self.label = label
        msg = f'Prompt not found: {prompt_key}'
        if label:
            msg += f' (label: {label})'
        super().__init__(msg)


class PromptConfigurationError(PromptError):
    """
    Error in prompt configuration.

    Raised when required configuration is missing or invalid.
    """


class PromptStoreError(PromptError):
    """
    Error from prompt store operations.

    Raised when prompt retrieval, parsing, or synchronization fails.
    """


class PromptCompilationError(PromptError):
    """
    Error compiling prompt templates.

    Raised when required variables are missing for prompt compilation.
    """

    def __init__(self, prompt_key: str, missing_variables: List[str]) -> None:
        """
        Initialize the exception with missing variable details.

        Args:
            prompt_key: Prompt key being compiled.
            missing_variables: List of missing variable names.
        """
        self.prompt_key = prompt_key
        self.missing_variables = missing_variables
        super().__init__(
            f'Missing variables for prompt {prompt_key}: {missing_variables}'
        )
