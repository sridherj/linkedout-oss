# SPDX-License-Identifier: Apache-2.0
"""Post-LLM validation pipeline."""
from typing import Any, Callable, List

from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class PostValidationError(Exception):
    """Raised when LLM output fails post-validation checks."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f'Post-validation failed with {len(errors)} error(s): {errors}')


def validate_llm_output(
    output: Any,
    validators: List[Callable[[Any], List[str]]],
) -> List[str]:
    """
    Run a list of validator functions against LLM output.

    Each validator receives the output and returns a list of error strings
    (empty list means valid).

    Args:
        output: The parsed LLM output to validate.
        validators: List of callables, each returning a list of error strings.

    Returns:
        Aggregated list of all validation error strings.
    """
    all_errors: List[str] = []
    for validator in validators:
        try:
            errors = validator(output)
            if errors:
                all_errors.extend(errors)
        except Exception as e:
            error_msg = f'Validator {validator.__name__} raised: {e}'
            logger.error(error_msg)
            all_errors.append(error_msg)
    return all_errors
