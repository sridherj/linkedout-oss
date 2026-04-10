# SPDX-License-Identifier: Apache-2.0
"""Controller/API layer for BU endpoints."""

import math
from typing import Annotated, Any, Dict, Generator

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from common.schemas.base_response_schema import PaginationLinks
from organization.schemas.bu_schema import BuSchema
from organization.schemas.bus_api_schema import (
    CreateBuRequestSchema,
    CreateBuResponseSchema,
    CreateBusRequestSchema,
    CreateBusResponseSchema,
    DeleteBuByIdRequestSchema,
    GetBuByIdRequestSchema,
    GetBuByIdResponseSchema,
    ListBusRequestSchema,
    ListBusResponseSchema,
    UpdateBuRequestSchema,
    UpdateBuResponseSchema,
)
from organization.services.bu_service import BuService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


# Router for BU endpoints
# BU is scoped by tenant_id
bus_router = APIRouter(
    prefix='/tenants/{tenant_id}/bus',
    tags=['business-units']
)


def _get_bu_service(
    request: Request,
    session_type: DbSessionType = DbSessionType.READ,
) -> Generator[BuService, None, None]:
    """
    Dependency to get BuService with appropriate session type.

    Args:
        request: The FastAPI request (provides app.state.db_manager).
        session_type: Type of database session (READ or WRITE)

    Yields:
        BuService: Service instance with database session
    """
    logger.debug(f'Requesting BuService with session type: {session_type.value}')
    db_manager = request.app.state.db_manager
    with db_manager.get_session(session_type) as session:
        logger.debug(f'Session {session} acquired for BuService')
        try:
            yield BuService(session)
        finally:
            logger.debug(f'BuService session {session} lifecycle complete')


def _get_write_bu_service(request: Request) -> Generator[BuService, None, None]:
    """Dependency for write operations."""
    yield from _get_bu_service(request, session_type=DbSessionType.WRITE)


class BuController:
    """
    Controller for BU API endpoints.

    Implements REST API patterns with:
    - Proper HTTP methods (GET, POST, PATCH, DELETE)
    - Pagination and filtering
    - HATEOAS links for pagination
    - OpenAPI documentation
    - Error handling

    Note: BU is scoped by tenant_id.
    """

    list_bus_summary = """
    List business units with filtering, sorting and pagination.

    Returns paginated list of business units with:
    - Full-text search in BU name
    - Sorting by various fields
    - HATEOAS pagination links
    """

    @staticmethod
    @bus_router.get(
        '',
        response_model=ListBusResponseSchema,
        summary='List business units with filtering and pagination',
        description=list_bus_summary,
    )
    def list_bus(
        request: Request,
        tenant_id: str,
        list_request: Annotated[ListBusRequestSchema, Query()],
        bu_service: BuService = Depends(_get_bu_service),
    ) -> ListBusResponseSchema:
        """List business units with filters."""
        # Populate path params
        list_request.tenant_id = tenant_id

        logger.info(f'Listing BUs for tenant: {tenant_id}')

        try:
            bus, total_count = bu_service.list_bus(list_request)

            if total_count > 0:
                response = BuController._get_paginated_response(
                    request=request,
                    tenant_id=tenant_id,
                    bus=bus,
                    total_count=total_count,
                    list_request=list_request,
                )

                logger.debug(
                    f'Returning {len(bus)} BUs '
                    f'(page {list_request.offset // list_request.limit + 1} '
                    f'of {response.page_count})'
                )
            else:
                logger.debug('No BUs found')
                response = ListBusResponseSchema(
                    bus=[],
                    total=0,
                    limit=list_request.limit,
                    offset=list_request.offset,
                    page_count=1,
                    links=None,
                    meta={
                        'sort_by': list_request.sort_by,
                        'sort_order': list_request.sort_order,
                        'search': list_request.search,
                    }
                )

            return response

        except Exception as e:
            logger.error(f'Error listing BUs: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to list BUs: {str(e)}'
            )

    @classmethod
    def _get_paginated_response(
        cls,
        request: Request,
        tenant_id: str,
        bus: list[BuSchema],
        total_count: int,
        list_request: ListBusRequestSchema,
    ) -> ListBusResponseSchema:
        """Build paginated response with HATEOAS links."""
        # Calculate page count
        page_count = (
            math.ceil(total_count / list_request.limit) if total_count > 0 else 1
        )

        # Build pagination links
        query_params = {
            'sort_by': list_request.sort_by,
            'sort_order': list_request.sort_order,
            'search': list_request.search,
        }

        links = cls._build_pagination_links(
            request=request,
            tenant_id=tenant_id,
            total=total_count,
            limit=list_request.limit,
            offset=list_request.offset,
            params=query_params,
        )

        return ListBusResponseSchema(
            bus=bus,
            total=total_count,
            limit=list_request.limit,
            offset=list_request.offset,
            page_count=page_count,
            links=links,
            meta={
                'sort_by': list_request.sort_by,
                'sort_order': list_request.sort_order,
                'search': list_request.search,
            },
        )

    @classmethod
    def _build_pagination_links(
        cls,
        request: Request,
        tenant_id: str,
        total: int,
        limit: int,
        offset: int,
        params: Dict[str, Any],
    ) -> PaginationLinks:
        """Build HATEOAS pagination links."""
        logger.debug(
            f'Building pagination links - total: {total}, limit: {limit}, offset: {offset}'
        )

        # Base URL with tenant_id
        base_url = f'{request.url.scheme}://{request.url.netloc}/tenants/{tenant_id}/bus'

        # Build query string
        query_params = []
        for k, v in params.items():
            if k not in ['limit', 'offset'] and v is not None:
                if isinstance(v, list):
                    for item in v:
                        query_params.append(f'{k}={item}')
                else:
                    query_params.append(f'{k}={v}')

        query_string = '&'.join(query_params)
        if query_string:
            query_string = '&' + query_string

        # Calculate pagination values
        page_count = math.ceil(total / limit) if total > 0 else 1
        has_prev = offset > 0
        has_next = offset + limit < total

        # Build links
        self_link = f'{base_url}?limit={limit}&offset={offset}{query_string}'
        first_link = f'{base_url}?limit={limit}&offset=0{query_string}'
        last_link = (
            f'{base_url}?limit={limit}&offset={(page_count - 1) * limit}{query_string}'
            if page_count > 1
            else None
        )
        prev_link = (
            f'{base_url}?limit={limit}&offset={max(0, offset - limit)}{query_string}'
            if has_prev
            else None
        )
        next_link = (
            f'{base_url}?limit={limit}&offset={offset + limit}{query_string}'
            if has_next
            else None
        )

        return PaginationLinks(
            self=self_link,
            first=first_link,
            last=last_link,
            prev=prev_link,
            next=next_link
        )

    create_bu_summary = """
    Create a new business unit.

    Creates a business unit with:
    - Required: name
    - Optional: description

    Returns the created BU with auto-generated ID and timestamps.
    """

    @staticmethod
    @bus_router.post(
        '',
        status_code=201,
        response_model=CreateBuResponseSchema,
        summary='Create a new business unit',
        description=create_bu_summary,
    )
    def create_bu(
        request: Request,
        tenant_id: str,
        create_request: Annotated[CreateBuRequestSchema, Body()],
        bu_service: BuService = Depends(_get_write_bu_service),
    ) -> CreateBuResponseSchema:
        """Create a new business unit."""
        # Populate path params
        create_request.tenant_id = tenant_id

        logger.info(f'Creating BU: {create_request.name} for tenant: {tenant_id}')

        try:
            created_bu = bu_service.create_bu(create_request)
            logger.info(f'BU created successfully: {created_bu.id}')
            return CreateBuResponseSchema(bu=created_bu)
        except Exception as e:
            logger.error(f'Error creating BU: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to create BU: {str(e)}'
            )

    create_bus_bulk_summary = """
    Create multiple new business units.

    Creates multiple business units in a single request.
    """

    @staticmethod
    @bus_router.post(
        '/bulk',
        status_code=201,
        response_model=CreateBusResponseSchema,
        summary='Create multiple new business units',
        description=create_bus_bulk_summary,
    )
    def create_bus_bulk(
        request: Request,
        tenant_id: str,
        create_request: Annotated[CreateBusRequestSchema, Body()],
        bu_service: BuService = Depends(_get_write_bu_service),
    ) -> CreateBusResponseSchema:
        """Create multiple new business units."""
        # Populate path params
        create_request.tenant_id = tenant_id

        logger.info(f'Creating {len(create_request.bus)} BUs for tenant: {tenant_id}')

        try:
            created_bus = bu_service.create_bus(create_request)
            logger.info(f'Successfully created {len(created_bus)} BUs')
            return CreateBusResponseSchema(bus=created_bus)
        except Exception as e:
            logger.error(f'Error creating BUs in bulk: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to create BUs: {str(e)}'
            )

    update_bu_summary = """
    Update a business unit by its ID.

    Supports partial updates - only provided fields are updated.
    """

    @staticmethod
    @bus_router.patch(
        '/{bu_id}',
        response_model=UpdateBuResponseSchema,
        summary='Update a business unit',
        description=update_bu_summary,
    )
    def update_bu(
        request: Request,
        tenant_id: str,
        bu_id: str,
        update_request: Annotated[UpdateBuRequestSchema, Body()],
        bu_service: BuService = Depends(_get_write_bu_service),
    ) -> UpdateBuResponseSchema:
        """Update a business unit."""
        # Populate path params
        update_request.tenant_id = tenant_id
        update_request.bu_id = bu_id

        logger.info(f'Updating BU {bu_id} for tenant: {tenant_id}')

        try:
            updated_bu = bu_service.update_bu(update_request)
            logger.info(f'BU updated successfully: {updated_bu.id}')
            return UpdateBuResponseSchema(bu=updated_bu)
        except ValueError as e:
            logger.warning(f'BU update failed - not found: {bu_id}')
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f'Error updating BU: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to update BU: {str(e)}'
            )

    get_bu_by_id_summary = """
    Get a business unit by its ID.

    Returns:
        GetBuByIdResponseSchema containing the business unit.

    Raises:
        HTTPException:
            - 404: Not Found - BU not found
            - 500: Internal Server Error - Unexpected server error

    Status Codes:
        - 200: Success - BU retrieved successfully
    """

    @staticmethod
    @bus_router.get(
        '/{bu_id}',
        response_model=GetBuByIdResponseSchema,
        summary='Get a business unit by its ID',
        description=get_bu_by_id_summary,
    )
    def get_bu_by_id(
        tenant_id: str,
        bu_id: str,
        get_request: Annotated[GetBuByIdRequestSchema, Query()],
        bu_service: BuService = Depends(_get_bu_service),
    ) -> GetBuByIdResponseSchema:
        """Get a business unit by ID."""
        # Populate path params
        get_request.tenant_id = tenant_id
        get_request.bu_id = bu_id

        logger.debug(f'Getting BU {bu_id} for tenant: {tenant_id}')

        try:
            bu = bu_service.get_bu_by_id(get_request)
            if not bu:
                logger.warning(f'BU not found: {bu_id}')
                raise HTTPException(
                    status_code=404,
                    detail=f'BU with ID {bu_id} not found'
                )
            return GetBuByIdResponseSchema(bu=bu)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Error getting BU {bu_id}: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to get BU: {str(e)}'
            )

    delete_bu_by_id_summary = """
    Delete a business unit by its ID.

    Returns:
        None

    Raises:
        HTTPException:
            - 404: Not Found - BU not found
            - 500: Internal Server Error - Unexpected server error

    Status Codes:
        - 204: Success - BU deleted successfully
    """

    @staticmethod
    @bus_router.delete(
        '/{bu_id}',
        status_code=204,
        summary='Delete a business unit by its ID',
        description=delete_bu_by_id_summary,
    )
    def delete_bu_by_id(
        tenant_id: str,
        bu_id: str,
        delete_request: Annotated[DeleteBuByIdRequestSchema, Query()],
        bu_service: BuService = Depends(_get_write_bu_service),
    ) -> None:
        """Delete a business unit by ID."""
        # Populate path params
        delete_request.tenant_id = tenant_id
        delete_request.bu_id = bu_id

        logger.info(f'Deleting BU {bu_id} for tenant: {tenant_id}')

        try:
            bu_service.delete_bu_by_id(delete_request)
            return Response(status_code=204)
        except ValueError as e:
            logger.warning(f'BU deletion failed - not found: {bu_id}')
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f'Error deleting BU {bu_id}: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to delete BU: {str(e)}'
            )


# Create controller instance
bu_controller = BuController()
