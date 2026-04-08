# SPDX-License-Identifier: Apache-2.0
"""Base response schemas."""
from typing import Annotated, Optional
from pydantic import BaseModel, Field


class BaseResponseSchema(BaseModel):
    """
    Base response schema for all API responses.
    
    This can be extended to include common response metadata.
    """
    pass


class PaginationLinks(BaseModel):
    """
    HATEOAS pagination links for API responses.
    
    Attributes:
        self: URL for the current page
        first: URL for the first page
        last: URL for the last page (optional)
        prev: URL for the previous page (optional)
        next: URL for the next page (optional)
    """
    self: str = Field(description='URL for the current page')
    first: str = Field(description='URL for the first page')
    last: Annotated[Optional[str], Field(default=None, description='URL for the last page')] = None
    prev: Annotated[Optional[str], Field(default=None, description='URL for the previous page')] = None
    next: Annotated[Optional[str], Field(default=None, description='URL for the next page')] = None


class PaginateResponseSchema(BaseResponseSchema):
    """
    Schema for paginated API responses.
    
    Attributes:
        total: Total number of items across all pages
        limit: Maximum number of items per page
        offset: Number of items skipped from the start
        page_count: Total number of pages
        links: Optional HATEOAS pagination links for navigation
    """
    total: int = Field(description='Total number of items across all pages')
    limit: int = Field(description='Maximum number of items per page')
    offset: int = Field(description='Number of items skipped from the start')
    page_count: Annotated[int, Field(default=1, description='Total number of pages')] = 1
    links: Annotated[Optional[PaginationLinks], Field(default=None, description='HATEOAS pagination links')] = None

