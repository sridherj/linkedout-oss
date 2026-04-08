# SPDX-License-Identifier: Apache-2.0
"""Base enums used across schemas."""
from enum import StrEnum


class SortOrder(StrEnum):
    """Sort order for queries."""
    ASC = 'asc'
    DESC = 'desc'

