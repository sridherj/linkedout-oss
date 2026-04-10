# SPDX-License-Identifier: Apache-2.0
"""Factory for creating CRUD API routers."""

import inspect
import math
from dataclasses import dataclass, field
from typing import Annotated, Any, Callable, Generator, List, Optional, Type

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from common.controllers.base_controller_utils import build_pagination_links
from common.services.base_service import BaseService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


def _inject_path_param(func: Callable, param_name: str) -> Callable:
    """Rewrite a function's __signature__ to add an explicit path parameter.

    FastAPI uses inspect.signature() to discover parameters.  When a factory
    builds endpoints whose path-param name is only known at runtime (e.g.
    ``{label_id}`` vs ``{lot_id}``), we cannot put a literal parameter in the
    ``def`` line.  This helper removes ``**kwargs`` from the visible signature
    and appends the named path parameter so FastAPI registers it correctly in
    routing *and* in the OpenAPI docs.

    The real function body should read the value via
    ``request.path_params[param_name]``.
    """
    sig = inspect.signature(func)
    non_kwargs = [
        p for p in sig.parameters.values()
        if p.kind != inspect.Parameter.VAR_KEYWORD
    ]
    new_param = inspect.Parameter(
        param_name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str,
    )
    # Insert before the first parameter that has a default value,
    # so the signature stays valid (no required arg after optional).
    insert_idx = next(
        (i for i, p in enumerate(non_kwargs) if p.default is not inspect.Parameter.empty),
        len(non_kwargs),
    )
    non_kwargs.insert(insert_idx, new_param)
    func.__signature__ = sig.replace(parameters=non_kwargs)
    return func


@dataclass
class CRUDRouterConfig:
    """
    Configuration for creating a CRUD router.

    Attributes:
        prefix: URL prefix for the router (e.g., '/tenants/{tenant_id}/bus/{bu_id}/lots')
        tags: OpenAPI tags for the router
        service_class: The service class to use
        entity_name: Singular entity name (e.g., 'lot')
        entity_name_plural: Plural entity name (e.g., 'lots')

        list_request_schema: Schema for list request
        list_response_schema: Schema for list response
        create_request_schema: Schema for create request
        create_response_schema: Schema for create response
        create_bulk_request_schema: Schema for bulk create request
        create_bulk_response_schema: Schema for bulk create response
        update_request_schema: Schema for update request
        update_response_schema: Schema for update response
        get_by_id_request_schema: Schema for get by ID request
        get_by_id_response_schema: Schema for get by ID response
        delete_by_id_request_schema: Schema for delete by ID request

        entity_id_param: Name of the entity ID path parameter (e.g., 'lot_id')
        meta_fields: List of filter field names to include in response meta
    """
    prefix: str
    tags: List[str]
    service_class: Type[BaseService]
    entity_name: str
    entity_name_plural: str

    # Schema classes
    list_request_schema: Type
    list_response_schema: Type
    create_request_schema: Type
    create_response_schema: Type
    create_bulk_request_schema: Type
    create_bulk_response_schema: Type
    update_request_schema: Type
    update_response_schema: Type
    get_by_id_request_schema: Type
    get_by_id_response_schema: Type
    delete_by_id_request_schema: Type

    entity_id_param: str = ''
    meta_fields: List[str] = field(default_factory=list)
    auth_dependency: Optional[Callable] = None

    def __post_init__(self):
        """Set defaults based on entity_name if not provided."""
        if not self.entity_id_param:
            self.entity_id_param = f'{self.entity_name}_id'


@dataclass
class CRUDRouterResult:
    """Result of create_crud_router.

    Attributes:
        router: The configured FastAPI APIRouter.
        get_service: Read-service dependency — expose in your controller module
            so tests can use ``app.dependency_overrides[get_service]``.
        get_write_service: Write-service dependency (same purpose).
    """
    router: APIRouter
    get_service: Callable
    get_write_service: Callable


def create_crud_router(config: CRUDRouterConfig) -> CRUDRouterResult:
    """
    Factory function to create a complete CRUD router with all endpoints.

    Creates endpoints for:
    - GET / - List entities with filters and pagination
    - POST / - Create a new entity
    - POST /bulk - Create multiple entities
    - GET /{entity_id} - Get entity by ID
    - PATCH /{entity_id} - Update entity
    - DELETE /{entity_id} - Delete entity

    Args:
        config: Configuration for the router

    Returns:
        CRUDRouterResult: Router and service dependencies for test overrides.
    """
    router_kwargs = {"prefix": config.prefix, "tags": config.tags}
    if config.auth_dependency:
        router_kwargs["dependencies"] = [Depends(config.auth_dependency)]
    router = APIRouter(**router_kwargs)

    # Dependency functions for service
    def _get_service(
        request: Request,
        session_type: DbSessionType = DbSessionType.READ,
    ) -> Generator[BaseService, None, None]:
        """Dependency to get service with appropriate session type."""
        logger.debug(f'Requesting {config.service_class.__name__} with session type: {session_type.value}')
        db_manager = request.app.state.db_manager
        with db_manager.get_session(session_type) as session:
            logger.debug(f'Session {session} acquired for {config.service_class.__name__}')
            try:
                yield config.service_class(session)
            finally:
                logger.debug(f'{config.service_class.__name__} session {session} lifecycle complete')

    def _get_write_service(request: Request) -> Generator[BaseService, None, None]:
        """Dependency for write operations."""
        yield from _get_service(request, session_type=DbSessionType.WRITE)

    def _get_paginated_response(
        request: Request,
        tenant_id: str,
        bu_id: str,
        items: list,
        total_count: int,
        list_request: Any,
    ):
        """Build paginated response with HATEOAS links."""
        page_count = math.ceil(total_count / list_request.limit) if total_count > 0 else 1

        # Build meta dict from configured meta fields
        meta = {}
        for field_name in config.meta_fields:
            meta[field_name] = getattr(list_request, field_name, None)

        # Build pagination links using shared utility
        links = build_pagination_links(
            request=request,
            entity_path=config.entity_name_plural,
            tenant_id=tenant_id,
            bu_id=bu_id,
            total=total_count,
            limit=list_request.limit,
            offset=list_request.offset,
            params=meta,
            prefix=config.prefix,
        )

        # Create response dict
        response_data = {
            config.entity_name_plural: items,
            'total': total_count,
            'limit': list_request.limit,
            'offset': list_request.offset,
            'page_count': page_count,
            'links': links,
            'meta': meta,
        }

        return config.list_response_schema(**response_data)

    # LIST endpoint
    @router.get(
        '',
        response_model=config.list_response_schema,
        summary=f'List {config.entity_name_plural} with filtering and pagination',
    )
    def list_entities(
        request: Request,
        tenant_id: str,
        bu_id: str,
        list_request: Annotated[config.list_request_schema, Query()],
        service: BaseService = Depends(_get_service),
    ):
        """List entities with filters."""
        list_request.tenant_id = tenant_id
        list_request.bu_id = bu_id

        logger.info(f'Listing {config.entity_name_plural} for tenant: {tenant_id}, bu: {bu_id}')

        try:
            items, total_count = service.list_entities(list_request)

            if total_count > 0:
                response = _get_paginated_response(
                    request=request,
                    tenant_id=tenant_id,
                    bu_id=bu_id,
                    items=items,
                    total_count=total_count,
                    list_request=list_request,
                )
            else:
                # Build empty meta
                meta = {field: getattr(list_request, field, None) for field in config.meta_fields}
                response_data = {
                    config.entity_name_plural: [],
                    'total': 0,
                    'limit': list_request.limit,
                    'offset': list_request.offset,
                    'page_count': 1,
                    'links': None,
                    'meta': meta,
                }
                response = config.list_response_schema(**response_data)

            return response

        except Exception as e:
            logger.error(f'Error listing {config.entity_name_plural}: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to list {config.entity_name_plural}: {str(e)}'
            )

    # CREATE endpoint
    @router.post(
        '',
        status_code=201,
        response_model=config.create_response_schema,
        summary=f'Create a new {config.entity_name}',
    )
    def create_entity(
        request: Request,
        tenant_id: str,
        bu_id: str,
        create_request: Annotated[config.create_request_schema, Body()],
        service: BaseService = Depends(_get_write_service),
    ):
        """Create a new entity."""
        create_request.tenant_id = tenant_id
        create_request.bu_id = bu_id

        logger.info(f'Creating {config.entity_name} for tenant: {tenant_id}, bu: {bu_id}')

        try:
            created_item = service.create_entity(create_request)
            logger.info(f'{config.entity_name.capitalize()} created successfully: {created_item.id}')
            return config.create_response_schema(**{config.entity_name: created_item})
        except Exception as e:
            logger.error(f'Error creating {config.entity_name}: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to create {config.entity_name}: {str(e)}'
            )

    # CREATE BULK endpoint
    @router.post(
        '/bulk',
        status_code=201,
        response_model=config.create_bulk_response_schema,
        summary=f'Create multiple new {config.entity_name_plural}',
    )
    def create_entities_bulk(
        request: Request,
        tenant_id: str,
        bu_id: str,
        create_request: Annotated[config.create_bulk_request_schema, Body()],
        service: BaseService = Depends(_get_write_service),
    ):
        """Create multiple new entities."""
        create_request.tenant_id = tenant_id
        create_request.bu_id = bu_id

        items_count = len(getattr(create_request, config.entity_name_plural, []))
        logger.info(f'Creating {items_count} {config.entity_name_plural} for tenant: {tenant_id}, bu: {bu_id}')

        try:
            created_items = service.create_entities_bulk(create_request)
            logger.info(f'Successfully created {len(created_items)} {config.entity_name_plural}')
            return config.create_bulk_response_schema(**{config.entity_name_plural: created_items})
        except Exception as e:
            logger.error(f'Error creating {config.entity_name_plural} in bulk: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to create {config.entity_name_plural}: {str(e)}'
            )

    # UPDATE endpoint
    def update_entity(
        request: Request,
        tenant_id: str,
        bu_id: str,
        update_request: Annotated[config.update_request_schema, Body()],
        service: BaseService = Depends(_get_write_service),
        **_kwargs,
    ):
        """Update an entity."""
        entity_id = request.path_params[config.entity_id_param]
        update_request.tenant_id = tenant_id
        update_request.bu_id = bu_id
        setattr(update_request, config.entity_id_param, entity_id)

        logger.info(f'Updating {config.entity_name} {entity_id} for tenant: {tenant_id}, bu: {bu_id}')

        try:
            updated_item = service.update_entity(update_request)
            logger.info(f'{config.entity_name.capitalize()} updated successfully: {updated_item.id}')
            return config.update_response_schema(**{config.entity_name: updated_item})
        except ValueError as e:
            logger.warning(f'{config.entity_name.capitalize()} update failed - not found: {entity_id}')
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f'Error updating {config.entity_name}: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to update {config.entity_name}: {str(e)}'
            )

    _inject_path_param(update_entity, config.entity_id_param)
    router.patch(
        '/{' + config.entity_id_param + '}',
        response_model=config.update_response_schema,
        summary=f'Update a {config.entity_name}',
    )(update_entity)

    # GET BY ID endpoint
    def get_entity_by_id(
        request: Request,
        tenant_id: str,
        bu_id: str,
        service: BaseService = Depends(_get_service),
        **_kwargs,
    ):
        """Get an entity by ID."""
        entity_id = request.path_params[config.entity_id_param]
        get_request = config.get_by_id_request_schema(
            tenant_id=tenant_id, bu_id=bu_id,
            **{config.entity_id_param: entity_id},
        )

        logger.debug(f'Getting {config.entity_name} {entity_id} for tenant: {tenant_id}, bu: {bu_id}')

        try:
            item = service.get_entity_by_id(get_request)
            if not item:
                logger.warning(f'{config.entity_name.capitalize()} not found: {entity_id}')
                raise HTTPException(
                    status_code=404,
                    detail=f'{config.entity_name.capitalize()} with ID {entity_id} not found'
                )
            return config.get_by_id_response_schema(**{config.entity_name: item})
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Error getting {config.entity_name} {entity_id}: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to get {config.entity_name}: {str(e)}'
            )

    _inject_path_param(get_entity_by_id, config.entity_id_param)
    router.get(
        '/{' + config.entity_id_param + '}',
        response_model=config.get_by_id_response_schema,
        summary=f'Get a {config.entity_name} by its ID',
    )(get_entity_by_id)

    # DELETE endpoint
    def delete_entity_by_id(
        request: Request,
        tenant_id: str,
        bu_id: str,
        service: BaseService = Depends(_get_write_service),
        **_kwargs,
    ):
        """Delete an entity by ID."""
        entity_id = request.path_params[config.entity_id_param]
        delete_request = config.delete_by_id_request_schema(
            tenant_id=tenant_id, bu_id=bu_id,
            **{config.entity_id_param: entity_id},
        )

        logger.info(f'Deleting {config.entity_name} {entity_id} for tenant: {tenant_id}, bu: {bu_id}')

        try:
            service.delete_entity_by_id(delete_request)
            return Response(status_code=204)
        except ValueError as e:
            logger.warning(f'{config.entity_name.capitalize()} deletion failed - not found: {entity_id}')
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f'Error deleting {config.entity_name} {entity_id}: {str(e)}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to delete {config.entity_name}: {str(e)}'
            )

    _inject_path_param(delete_entity_by_id, config.entity_id_param)
    router.delete(
        '/{' + config.entity_id_param + '}',
        status_code=204,
        summary=f'Delete a {config.entity_name} by its ID',
    )(delete_entity_by_id)

    return CRUDRouterResult(
        router=router,
        get_service=_get_service,
        get_write_service=_get_write_service,
    )
