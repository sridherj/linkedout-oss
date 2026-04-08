# SPDX-License-Identifier: Apache-2.0
"""API schemas for tenant endpoints."""

from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from organization.schemas.tenant_schema import TenantSchema


class TenantSortByFields(StrEnum):
    """Fields that can be used for sorting tenants."""

    NAME = 'name'
    CREATED_AT = 'created_at'
    UPDATED_AT = 'updated_at'


class ListTenantsRequestSchema(PaginateRequestSchema):
    """
    Request schema for listing tenants with filters and pagination.

    Attributes:
        sort_by: Field to sort by
        sort_order: Sort direction (asc/desc)
        search: Search in tenant name
    """

    sort_by: Annotated[
        Optional[TenantSortByFields],
        Field(default=TenantSortByFields.NAME)
    ] = TenantSortByFields.NAME
    sort_order: Annotated[Optional[SortOrder], Field(default=SortOrder.ASC)] = SortOrder.ASC

    search: Annotated[
        Optional[str], Field(default=None, description='Search in tenant name')
    ] = None


class ListTenantsResponseSchema(PaginateResponseSchema):
    """
    Response schema for listing tenants.

    Attributes:
        tenants: List of tenants matching the filter criteria
        meta: Optional metadata about the request parameters used
    """

    tenants: List[TenantSchema] = Field(
        default_factory=list, description='List of tenants'
    )
    meta: Optional[dict] = Field(default=None, description='Request metadata (filters, sorting)')


class CreateTenantRequestSchema(BaseRequestSchema):
    """
    Request schema for creating a new tenant.

    Attributes:
        name: The name of the tenant organization (required)
        description: Optional description of the tenant
    """

    name: Annotated[str, Field(..., description='The name of the tenant organization')]
    description: Annotated[
        Optional[str],
        Field(None, description='Optional description of the tenant')
    ] = None


class CreateTenantResponseSchema(BaseResponseSchema):
    """Response schema for tenant creation."""

    tenant: Annotated[TenantSchema, Field(description='Created tenant')] = None


class CreateTenantsRequestSchema(BaseRequestSchema):
    """
    Request schema for creating multiple tenants in bulk.

    Attributes:
        tenants: List of tenants to create
    """

    tenants: Annotated[
        List[CreateTenantRequestSchema],
        Field(..., description='List of tenants to create')
    ]


class CreateTenantsResponseSchema(BaseResponseSchema):
    """Response schema for bulk tenant creation."""

    tenants: Annotated[List[TenantSchema], Field(description='Created tenants')] = []


class UpdateTenantRequestSchema(BaseRequestSchema):
    """
    Request schema for updating a tenant.

    All fields except tenant_id are optional.
    Only provided fields will be updated.
    """

    tenant_id: Annotated[Optional[str], Field(None, description='Tenant ID')] = None

    name: Annotated[Optional[str], Field(None, description='Tenant name')] = None
    description: Annotated[Optional[str], Field(None, description='Tenant description')] = None


class UpdateTenantResponseSchema(BaseResponseSchema):
    """Response schema for tenant update."""

    tenant: Annotated[TenantSchema, Field(description='Updated tenant')] = None


class GetTenantByIdRequestSchema(BaseRequestSchema):
    """Request schema for getting a tenant by ID."""

    tenant_id: Annotated[Optional[str], Field(None, description='Tenant ID')] = None


class GetTenantByIdResponseSchema(BaseResponseSchema):
    """Response schema for getting a tenant by ID."""

    tenant: Annotated[TenantSchema, Field(description='Tenant details')] = None


class DeleteTenantByIdRequestSchema(BaseRequestSchema):
    """Request schema for deleting a tenant by ID."""

    tenant_id: Annotated[Optional[str], Field(None, description='Tenant ID')] = None
