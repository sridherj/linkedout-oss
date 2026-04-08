# SPDX-License-Identifier: Apache-2.0
"""Controller/API layer for Tenant endpoints."""

import math
from typing import Annotated, Any, Dict, Generator

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from common.schemas.base_response_schema import PaginationLinks
from organization.schemas.tenant_schema import TenantSchema
from organization.schemas.tenants_api_schema import (
    CreateTenantRequestSchema,
    CreateTenantResponseSchema,
    CreateTenantsRequestSchema,
    CreateTenantsResponseSchema,
    DeleteTenantByIdRequestSchema,
    GetTenantByIdRequestSchema,
    GetTenantByIdResponseSchema,
    ListTenantsRequestSchema,
    ListTenantsResponseSchema,
    UpdateTenantRequestSchema,
    UpdateTenantResponseSchema,
)
from organization.services.tenant_service import TenantService
from shared.infra.db.db_session_manager import DbSessionType, db_session_manager
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


# Router for tenant endpoints
# Tenant is the top-level entity with no scoping
tenants_router = APIRouter(
    prefix='/tenants',
    tags=['tenants']
)


def _get_tenant_service(
    session_type: DbSessionType = DbSessionType.READ,
) -> Generator[TenantService, None, None]:
    """
    Dependency to get TenantService with appropriate session type.

    Args:
        session_type: Type of database session (READ or WRITE)

    Yields:
        TenantService: Service instance with database session
    """
    logger.debug(f'Requesting TenantService with session type: {session_type.value}')
    with db_session_manager.get_session(session_type) as session:
        logger.debug(f'Session {session} acquired for TenantService')
        try:
            yield TenantService(session)
        finally:
            logger.debug(f'TenantService session {session} lifecycle complete')


def _get_write_tenant_service() -> Generator[TenantService, None, None]:
    """Dependency for write operations."""
    yield from _get_tenant_service(session_type=DbSessionType.WRITE)


class TenantController:
    """
    Controller for Tenant API endpoints.

    Implements REST API patterns with:
    - Proper HTTP methods (GET, POST, PATCH, DELETE)
    - Pagination and filtering
    - HATEOAS links for pagination
    - OpenAPI documentation
    - Error handling

    Note: Tenant is the top-level entity with no scoping.
    """

    list_tenants_summary = """
    List tenants with filtering, sorting and pagination.

    Returns paginated list of tenants with:
    - Full-text search in tenant name
    - Sorting by various fields
    - HATEOAS pagination links
    """

    @staticmethod
    @tenants_router.get(
        '',
        response_model=ListTenantsResponseSchema,
        summary='List tenants with filtering and pagination',
        description=list_tenants_summary,
    )
    def list_tenants(
        request: Request,
        list_request: Annotated[ListTenantsRequestSchema, Query()],
        tenant_service: TenantService = Depends(_get_tenant_service),
    ) -> ListTenantsResponseSchema:
        """List tenants with filters."""
        logger.info('Listing tenants')

        try:
            tenants, total_count = tenant_service.list_tenants(list_request)

            if total_count > 0:
                response = TenantController._get_paginated_response(
                    request=request,
                    tenants=tenants,
                    total_count=total_count,
                    list_request=list_request,
                )

                logger.debug(
                    f'Returning {len(tenants)} tenants '
                    f'(page {list_request.offset // list_request.limit + 1} '
                    f'of {response.page_count})'
                )
            else:
                logger.debug('No tenants found')
                response = ListTenantsResponseSchema(
                    tenants=[],
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
            logger.error(f'Error listing tenants: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to list tenants: {str(e)}'
            )

    @classmethod
    def _get_paginated_response(
        cls,
        request: Request,
        tenants: list[TenantSchema],
        total_count: int,
        list_request: ListTenantsRequestSchema,
    ) -> ListTenantsResponseSchema:
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
            total=total_count,
            limit=list_request.limit,
            offset=list_request.offset,
            params=query_params,
        )

        return ListTenantsResponseSchema(
            tenants=tenants,
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
        total: int,
        limit: int,
        offset: int,
        params: Dict[str, Any],
    ) -> PaginationLinks:
        """Build HATEOAS pagination links."""
        logger.debug(
            f'Building pagination links - total: {total}, limit: {limit}, offset: {offset}'
        )

        # Base URL
        base_url = f'{request.url.scheme}://{request.url.netloc}/tenants'

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

    create_tenant_summary = """
    Create a new tenant.

    Creates a tenant with:
    - Required: name
    - Optional: description

    Returns the created tenant with auto-generated ID and timestamps.
    """

    @staticmethod
    @tenants_router.post(
        '',
        status_code=201,
        response_model=CreateTenantResponseSchema,
        summary='Create a new tenant',
        description=create_tenant_summary,
    )
    def create_tenant(
        request: Request,
        create_request: Annotated[CreateTenantRequestSchema, Body()],
        tenant_service: TenantService = Depends(_get_write_tenant_service),
    ) -> CreateTenantResponseSchema:
        """Create a new tenant."""
        logger.info(f'Creating tenant: {create_request.name}')

        try:
            created_tenant = tenant_service.create_tenant(create_request)
            logger.info(f'Tenant created successfully: {created_tenant.id}')
            return CreateTenantResponseSchema(tenant=created_tenant)
        except Exception as e:
            logger.error(f'Error creating tenant: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to create tenant: {str(e)}'
            )

    create_tenants_bulk_summary = """
    Create multiple new tenants.

    Creates multiple tenants in a single request.
    """

    @staticmethod
    @tenants_router.post(
        '/bulk',
        status_code=201,
        response_model=CreateTenantsResponseSchema,
        summary='Create multiple new tenants',
        description=create_tenants_bulk_summary,
    )
    def create_tenants_bulk(
        request: Request,
        create_request: Annotated[CreateTenantsRequestSchema, Body()],
        tenant_service: TenantService = Depends(_get_write_tenant_service),
    ) -> CreateTenantsResponseSchema:
        """Create multiple new tenants."""
        logger.info(f'Creating {len(create_request.tenants)} tenants')

        try:
            created_tenants = tenant_service.create_tenants(create_request)
            logger.info(f'Successfully created {len(created_tenants)} tenants')
            return CreateTenantsResponseSchema(tenants=created_tenants)
        except Exception as e:
            logger.error(f'Error creating tenants in bulk: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to create tenants: {str(e)}'
            )

    update_tenant_summary = """
    Update a tenant by its ID.

    Supports partial updates - only provided fields are updated.
    """

    @staticmethod
    @tenants_router.patch(
        '/{tenant_id}',
        response_model=UpdateTenantResponseSchema,
        summary='Update a tenant',
        description=update_tenant_summary,
    )
    def update_tenant(
        request: Request,
        tenant_id: str,
        update_request: Annotated[UpdateTenantRequestSchema, Body()],
        tenant_service: TenantService = Depends(_get_write_tenant_service),
    ) -> UpdateTenantResponseSchema:
        """Update a tenant."""
        # Populate path params
        update_request.tenant_id = tenant_id

        logger.info(f'Updating tenant {tenant_id}')

        try:
            updated_tenant = tenant_service.update_tenant(update_request)
            logger.info(f'Tenant updated successfully: {updated_tenant.id}')
            return UpdateTenantResponseSchema(tenant=updated_tenant)
        except ValueError as e:
            logger.warning(f'Tenant update failed - not found: {tenant_id}')
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f'Error updating tenant: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to update tenant: {str(e)}'
            )

    get_tenant_by_id_summary = """
    Get a tenant by its ID.

    Returns:
        GetTenantByIdResponseSchema containing the tenant.

    Raises:
        HTTPException:
            - 404: Not Found - Tenant not found
            - 500: Internal Server Error - Unexpected server error

    Status Codes:
        - 200: Success - Tenant retrieved successfully
    """

    @staticmethod
    @tenants_router.get(
        '/{tenant_id}',
        response_model=GetTenantByIdResponseSchema,
        summary='Get a tenant by its ID',
        description=get_tenant_by_id_summary,
    )
    def get_tenant_by_id(
        tenant_id: str,
        get_request: Annotated[GetTenantByIdRequestSchema, Query()],
        tenant_service: TenantService = Depends(_get_tenant_service),
    ) -> GetTenantByIdResponseSchema:
        """Get a tenant by ID."""
        # Populate path params
        get_request.tenant_id = tenant_id

        logger.debug(f'Getting tenant {tenant_id}')

        try:
            tenant = tenant_service.get_tenant_by_id(get_request)
            if not tenant:
                logger.warning(f'Tenant not found: {tenant_id}')
                raise HTTPException(
                    status_code=404,
                    detail=f'Tenant with ID {tenant_id} not found'
                )
            return GetTenantByIdResponseSchema(tenant=tenant)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Error getting tenant {tenant_id}: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to get tenant: {str(e)}'
            )

    delete_tenant_by_id_summary = """
    Delete a tenant by its ID.

    Returns:
        None

    Raises:
        HTTPException:
            - 404: Not Found - Tenant not found
            - 500: Internal Server Error - Unexpected server error

    Status Codes:
        - 204: Success - Tenant deleted successfully
    """

    @staticmethod
    @tenants_router.delete(
        '/{tenant_id}',
        status_code=204,
        summary='Delete a tenant by its ID',
        description=delete_tenant_by_id_summary,
    )
    def delete_tenant_by_id(
        tenant_id: str,
        delete_request: Annotated[DeleteTenantByIdRequestSchema, Query()],
        tenant_service: TenantService = Depends(_get_write_tenant_service),
    ) -> None:
        """Delete a tenant by ID."""
        # Populate path params
        delete_request.tenant_id = tenant_id

        logger.info(f'Deleting tenant {tenant_id}')

        try:
            tenant_service.delete_tenant_by_id(delete_request)
            return Response(status_code=204)
        except ValueError as e:
            logger.warning(f'Tenant deletion failed - not found: {tenant_id}')
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f'Error deleting tenant {tenant_id}: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to delete tenant: {str(e)}'
            )


# Create controller instance
tenant_controller = TenantController()
