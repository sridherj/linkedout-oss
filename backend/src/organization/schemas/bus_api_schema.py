# SPDX-License-Identifier: Apache-2.0
"""API schemas for business unit endpoints."""

from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from organization.schemas.bu_schema import BuSchema


class BuSortByFields(StrEnum):
    """Fields that can be used for sorting business units."""

    NAME = 'name'
    CREATED_AT = 'created_at'
    UPDATED_AT = 'updated_at'


class ListBusRequestSchema(PaginateRequestSchema):
    """
    Request schema for listing business units with filters and pagination.

    Attributes:
        tenant_id: Tenant ID (populated by controller)
        sort_by: Field to sort by
        sort_order: Sort direction (asc/desc)
        search: Search in BU name
    """

    tenant_id: Annotated[Optional[str], Field(None, description='Tenant ID')] = None

    sort_by: Annotated[
        Optional[BuSortByFields],
        Field(default=BuSortByFields.NAME)
    ] = BuSortByFields.NAME
    sort_order: Annotated[Optional[SortOrder], Field(default=SortOrder.ASC)] = SortOrder.ASC

    search: Annotated[
        Optional[str], Field(default=None, description='Search in BU name')
    ] = None


class ListBusResponseSchema(PaginateResponseSchema):
    """
    Response schema for listing business units.

    Attributes:
        bus: List of business units matching the filter criteria
        meta: Optional metadata about the request parameters used
    """

    bus: List[BuSchema] = Field(
        default_factory=list, description='List of business units'
    )
    meta: Optional[dict] = Field(default=None, description='Request metadata (filters, sorting)')


class CreateBuRequestSchema(BaseRequestSchema):
    """
    Request schema for creating a new business unit.

    Attributes:
        tenant_id: Tenant ID (populated by controller)
        name: The name of the business unit (required)
        description: Optional description of the business unit
    """

    tenant_id: Annotated[Optional[str], Field(None, description='Tenant ID')] = None

    name: Annotated[str, Field(..., description='The name of the business unit')]
    description: Annotated[
        Optional[str],
        Field(None, description='Optional description of the business unit')
    ] = None


class CreateBuResponseSchema(BaseResponseSchema):
    """Response schema for BU creation."""

    bu: Annotated[BuSchema, Field(description='Created business unit')] = None


class CreateBusRequestSchema(BaseRequestSchema):
    """
    Request schema for creating multiple business units in bulk.

    Attributes:
        tenant_id: Tenant ID (populated by controller)
        bus: List of business units to create
    """

    tenant_id: Annotated[Optional[str], Field(None, description='Tenant ID')] = None

    bus: Annotated[
        List[CreateBuRequestSchema],
        Field(..., description='List of business units to create')
    ]


class CreateBusResponseSchema(BaseResponseSchema):
    """Response schema for bulk BU creation."""

    bus: Annotated[List[BuSchema], Field(description='Created business units')] = []


class UpdateBuRequestSchema(BaseRequestSchema):
    """
    Request schema for updating a business unit.

    All fields except tenant_id and bu_id are optional.
    Only provided fields will be updated.
    """

    tenant_id: Annotated[Optional[str], Field(None, description='Tenant ID')] = None
    bu_id: Annotated[Optional[str], Field(None, description='Business unit ID')] = None

    name: Annotated[Optional[str], Field(None, description='BU name')] = None
    description: Annotated[Optional[str], Field(None, description='BU description')] = None


class UpdateBuResponseSchema(BaseResponseSchema):
    """Response schema for BU update."""

    bu: Annotated[BuSchema, Field(description='Updated business unit')] = None


class GetBuByIdRequestSchema(BaseRequestSchema):
    """Request schema for getting a business unit by ID."""

    tenant_id: Annotated[Optional[str], Field(None, description='Tenant ID')] = None
    bu_id: Annotated[Optional[str], Field(None, description='Business unit ID')] = None


class GetBuByIdResponseSchema(BaseResponseSchema):
    """Response schema for getting a business unit by ID."""

    bu: Annotated[BuSchema, Field(description='Business unit details')] = None


class DeleteBuByIdRequestSchema(BaseRequestSchema):
    """Request schema for deleting a business unit by ID."""

    tenant_id: Annotated[Optional[str], Field(None, description='Tenant ID')] = None
    bu_id: Annotated[Optional[str], Field(None, description='Business unit ID')] = None
