# SPDX-License-Identifier: Apache-2.0
"""Custom exceptions for the LLM Manager module."""

from __future__ import annotations


class LLMError(Exception):
    """
    Base exception for LLM errors.

    All LLM-related exceptions inherit from this class, allowing
    callers to catch all LLM errors with a single except clause.
    """

    pass


class LLMConfigurationError(LLMError):
    """
    Error in LLM configuration.

    Raised when required configuration is missing or invalid,
    such as missing Azure endpoint or invalid temperature value.
    """

    pass


class LLMProviderError(LLMError):
    """
    Error from the LLM provider.

    Raised when the LLM API call fails due to provider issues
    such as rate limits, authentication errors, or service outages.
    """

    pass


class LLMParsingError(LLMError):
    """
    Error parsing LLM response.

    Raised when the LLM response cannot be parsed into the expected
    format, particularly for structured output calls where the response
    doesn't match the expected Pydantic model.
    """

    pass
