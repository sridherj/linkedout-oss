# SPDX-License-Identifier: Apache-2.0
"""Controller for RoleAlias endpoints.

Hand-written (not CRUDRouterFactory) because RoleAlias is a shared entity
with no tenant/BU scoping.
"""
from typing import Annotated, Generator

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from linkedout.role_alias.schemas.role_alias_api_schema import (
    CreateRoleAliasRequestSchema,
    CreateRoleAliasResponseSchema,
    CreateRoleAliasesRequestSchema,
    CreateRoleAliasesResponseSchema,
    GetRoleAliasByIdResponseSchema,
    ListRoleAliasesRequestSchema,
    ListRoleAliasesResponseSchema,
    UpdateRoleAliasRequestSchema,
    UpdateRoleAliasResponseSchema,
)
from linkedout.role_alias.services.role_alias_service import RoleAliasService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

role_aliases_router = APIRouter(
    prefix='/role-aliases',
    tags=['role-aliases'],
)


def _get_role_alias_service(
    request: Request,
    session_type: DbSessionType = DbSessionType.READ,
) -> Generator[RoleAliasService, None, None]:
    db_manager = request.app.state.db_manager
    with db_manager.get_session(session_type) as session:
        yield RoleAliasService(session)


def _get_write_role_alias_service(request: Request) -> Generator[RoleAliasService, None, None]:
    yield from _get_role_alias_service(request, session_type=DbSessionType.WRITE)


@role_aliases_router.get(
    '',
    response_model=ListRoleAliasesResponseSchema,
    summary='List role aliases with filtering and pagination',
)
def list_role_aliases(
    list_request: Annotated[ListRoleAliasesRequestSchema, Query()],
    service: RoleAliasService = Depends(_get_role_alias_service),
) -> ListRoleAliasesResponseSchema:
    try:
        items, total_count = service.list_role_aliases(list_request)
        return ListRoleAliasesResponseSchema(
            role_aliases=items,
            total=total_count,
            limit=list_request.limit,
            offset=list_request.offset,
            page_count=max(1, -(-total_count // list_request.limit)),
            links=None,
            meta={},
        )
    except Exception as e:
        logger.error(f'Error listing role aliases: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to list role aliases: {str(e)}')


@role_aliases_router.post(
    '',
    status_code=201,
    response_model=CreateRoleAliasResponseSchema,
    summary='Create a role alias',
)
def create_role_alias(
    create_request: Annotated[CreateRoleAliasRequestSchema, Body()],
    service: RoleAliasService = Depends(_get_write_role_alias_service),
) -> CreateRoleAliasResponseSchema:
    try:
        created = service.create_role_alias(create_request)
        return CreateRoleAliasResponseSchema(role_alias=created)
    except Exception as e:
        logger.error(f'Error creating role alias: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create role alias: {str(e)}')


@role_aliases_router.post(
    '/bulk',
    status_code=201,
    response_model=CreateRoleAliasesResponseSchema,
    summary='Create multiple role aliases',
)
def create_role_aliases_bulk(
    create_request: Annotated[CreateRoleAliasesRequestSchema, Body()],
    service: RoleAliasService = Depends(_get_write_role_alias_service),
) -> CreateRoleAliasesResponseSchema:
    try:
        created = service.create_role_aliases_bulk(create_request)
        return CreateRoleAliasesResponseSchema(role_aliases=created)
    except Exception as e:
        logger.error(f'Error creating role aliases in bulk: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create role aliases: {str(e)}')


@role_aliases_router.get(
    '/{role_alias_id}',
    response_model=GetRoleAliasByIdResponseSchema,
    summary='Get a role alias by ID',
)
def get_role_alias_by_id(
    role_alias_id: str,
    service: RoleAliasService = Depends(_get_role_alias_service),
) -> GetRoleAliasByIdResponseSchema:
    item = service.get_role_alias_by_id(role_alias_id)
    if not item:
        raise HTTPException(status_code=404, detail=f'RoleAlias with ID {role_alias_id} not found')
    return GetRoleAliasByIdResponseSchema(role_alias=item)


@role_aliases_router.patch(
    '/{role_alias_id}',
    response_model=UpdateRoleAliasResponseSchema,
    summary='Update a role alias',
)
def update_role_alias(
    role_alias_id: str,
    update_request: Annotated[UpdateRoleAliasRequestSchema, Body()],
    service: RoleAliasService = Depends(_get_write_role_alias_service),
) -> UpdateRoleAliasResponseSchema:
    try:
        updated = service.update_role_alias(role_alias_id, update_request)
        return UpdateRoleAliasResponseSchema(role_alias=updated)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error updating role alias: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to update role alias: {str(e)}')


@role_aliases_router.delete(
    '/{role_alias_id}',
    status_code=204,
    summary='Delete a role alias',
)
def delete_role_alias(
    role_alias_id: str,
    service: RoleAliasService = Depends(_get_write_role_alias_service),
):
    try:
        service.delete_role_alias_by_id(role_alias_id)
        return Response(status_code=204)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error deleting role alias: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to delete role alias: {str(e)}')
