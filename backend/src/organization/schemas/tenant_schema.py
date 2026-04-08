# SPDX-License-Identifier: Apache-2.0
"""Core tenant schema."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class TenantSchema(BaseModel):
    """
    Schema representing a tenant organization.

    A tenant is the top-level organizational unit in the system.
    It can have multiple business units.

    Attributes:
        id: Unique identifier for the tenant (tenant_ prefix)
        name: The name of the tenant organization
        description: Optional description of the tenant
        created_at: When the record was created
        updated_at: When the record was last updated
    """

    # Identifiers
    id: Annotated[str, Field(description='Unique identifier for the tenant')]

    # Basic Information
    name: Annotated[str, Field(description='The name of the tenant organization')]
    description: Annotated[
        str | None,
        Field(description='Optional description of the tenant')
    ] = None

    # System Timestamps
    created_at: Annotated[datetime, Field(description='Creation timestamp')]
    updated_at: Annotated[datetime, Field(description='Last update timestamp')]

    model_config = ConfigDict(from_attributes=True)