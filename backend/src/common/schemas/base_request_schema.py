# SPDX-License-Identifier: Apache-2.0
"""Base request schemas."""
from typing import Annotated, Optional
from pydantic import BaseModel, Field

from shared.auth.dependencies.schemas.auth_context import AuthContext


class BaseRequestSchema(BaseModel):
    """
    Base request schema for all API requests.

    Attributes:
        auth_context: Optional authentication context (populated by auth middleware)
    """
    auth_context: Optional[AuthContext] = None


class PaginateRequestSchema(BaseRequestSchema):
    """
    Base schema for paginated requests.
    
    Provides standard pagination parameters.
    
    Attributes:
        limit: Maximum number of items to return per page
        offset: Number of items to skip from the start
    """
    limit: Annotated[int, Field(default=20, ge=1, le=100, description='Items per page (1-100)')] = 20
    offset: Annotated[int, Field(default=0, ge=0, description='Items to skip from start')] = 0

