# SPDX-License-Identifier: Apache-2.0
"""Core business unit schema."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class BuSchema(BaseModel):
    """
    Schema representing a business unit within a tenant.

    A Business Unit (BU) is an administrative unit within a tenant.
    It allows different BUs to have different sets of definitions for
    grades, sizes for different commodities/varieties.

    Attributes:
        id: Unique identifier for the BU (bu_ prefix)
        tenant_id: The tenant this BU belongs to
        name: The name of the business unit
        description: Optional description of the business unit
        created_at: When the record was created
        updated_at: When the record was last updated
    """

    # Identifiers
    id: Annotated[str, Field(description='Unique identifier for the business unit')]
    tenant_id: Annotated[str, Field(description='Tenant ID')]

    # Basic Information
    name: Annotated[str, Field(description='The name of the business unit')]
    description: Annotated[
        str | None,
        Field(description='Optional description of the business unit')
    ] = None

    # System Timestamps
    created_at: Annotated[datetime, Field(description='Creation timestamp')]
    updated_at: Annotated[datetime, Field(description='Last update timestamp')]

    model_config = ConfigDict(from_attributes=True)