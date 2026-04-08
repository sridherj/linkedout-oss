# SPDX-License-Identifier: Apache-2.0
"""Base mixins for CRUD API schemas to reduce repetition."""

from typing import Annotated, Optional

from pydantic import BaseModel, Field

from common.schemas.base_enums_schemas import SortOrder


class TenantBuRequestMixin(BaseModel):
    """
    Mixin providing tenant and business unit fields for requests.

    These fields are typically populated by the controller from path parameters.
    """
    tenant_id: Annotated[Optional[str], Field(None, description='Tenant ID')] = None
    bu_id: Annotated[Optional[str], Field(None, description='Business unit ID')] = None


class SortableRequestMixin(BaseModel):
    """
    Mixin providing common sorting fields.

    Subclasses should define their own sort_by field with entity-specific enum.
    """
    sort_order: Annotated[Optional[SortOrder], Field(default=SortOrder.ASC)] = SortOrder.ASC


class ActiveFilterMixin(BaseModel):
    """Mixin providing is_active filter field."""
    is_active: Annotated[
        Optional[bool], Field(default=None, description='Filter by active status')
    ] = None
