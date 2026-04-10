# SPDX-License-Identifier: Apache-2.0
"""Controller for CompanyAlias endpoints (shared, no tenant/BU scoping)."""
import math
from typing import Annotated, Generator

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from common.controllers.base_controller_utils import create_service_dependency
from common.schemas.base_response_schema import PaginationLinks
from linkedout.company_alias.schemas.company_alias_api_schema import (
    CreateCompanyAliasRequestSchema,
    CreateCompanyAliasResponseSchema,
    CreateCompanyAliasesRequestSchema,
    CreateCompanyAliasesResponseSchema,
    DeleteCompanyAliasByIdRequestSchema,
    GetCompanyAliasByIdRequestSchema,
    GetCompanyAliasByIdResponseSchema,
    ListCompanyAliasesRequestSchema,
    ListCompanyAliasesResponseSchema,
    UpdateCompanyAliasRequestSchema,
    UpdateCompanyAliasResponseSchema,
)
from linkedout.company_alias.services.company_alias_service import CompanyAliasService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

company_aliases_router = APIRouter(
    prefix='/company-aliases',
    tags=['company-aliases'],
)

_META_FIELDS = [
    'sort_by', 'sort_order', 'alias_name', 'company_id', 'source',
]


def _get_company_alias_service(request: Request) -> Generator[CompanyAliasService, None, None]:
    yield from create_service_dependency(request, CompanyAliasService, DbSessionType.READ)


def _get_write_company_alias_service(request: Request) -> Generator[CompanyAliasService, None, None]:
    yield from create_service_dependency(request, CompanyAliasService, DbSessionType.WRITE)


def _build_pagination_links(
    request: Request,
    total: int,
    limit: int,
    offset: int,
    params: dict,
) -> PaginationLinks:
    """Build HATEOAS pagination links for company aliases."""
    base_url = f'{request.url.scheme}://{request.url.netloc}/company-aliases'

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

    page_count = math.ceil(total / limit) if total > 0 else 1
    has_prev = offset > 0
    has_next = offset + limit < total

    return PaginationLinks(
        self=f'{base_url}?limit={limit}&offset={offset}{query_string}',
        first=f'{base_url}?limit={limit}&offset=0{query_string}',
        last=f'{base_url}?limit={limit}&offset={(page_count - 1) * limit}{query_string}' if page_count > 1 else None,
        prev=f'{base_url}?limit={limit}&offset={max(0, offset - limit)}{query_string}' if has_prev else None,
        next=f'{base_url}?limit={limit}&offset={offset + limit}{query_string}' if has_next else None,
    )


@company_aliases_router.get(
    '',
    response_model=ListCompanyAliasesResponseSchema,
    summary='List company aliases with filtering and pagination',
)
def list_company_aliases(
    request: Request,
    list_request: Annotated[ListCompanyAliasesRequestSchema, Query()],
    service: CompanyAliasService = Depends(_get_company_alias_service),
) -> ListCompanyAliasesResponseSchema:
    """List company aliases with filters."""
    logger.info('Listing company aliases')

    try:
        company_aliases, total_count = service.list_company_aliases(list_request)

        meta = {field: getattr(list_request, field, None) for field in _META_FIELDS}

        if total_count > 0:
            page_count = math.ceil(total_count / list_request.limit)
            links = _build_pagination_links(
                request=request,
                total=total_count,
                limit=list_request.limit,
                offset=list_request.offset,
                params=meta,
            )
            return ListCompanyAliasesResponseSchema(
                company_aliases=company_aliases,
                total=total_count,
                limit=list_request.limit,
                offset=list_request.offset,
                page_count=page_count,
                links=links,
                meta=meta,
            )
        else:
            return ListCompanyAliasesResponseSchema(
                company_aliases=[],
                total=0,
                limit=list_request.limit,
                offset=list_request.offset,
                page_count=1,
                links=None,
                meta=meta,
            )
    except Exception as e:
        logger.error(f'Error listing company aliases: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to list company aliases: {str(e)}')


@company_aliases_router.post(
    '',
    status_code=201,
    response_model=CreateCompanyAliasResponseSchema,
    summary='Create a new company alias',
)
def create_company_alias(
    request: Request,
    create_request: Annotated[CreateCompanyAliasRequestSchema, Body()],
    service: CompanyAliasService = Depends(_get_write_company_alias_service),
) -> CreateCompanyAliasResponseSchema:
    """Create a new company alias."""
    logger.info(f'Creating company alias: {create_request.alias_name}')

    try:
        created = service.create_company_alias(create_request)
        logger.info(f'Company alias created successfully: {created.id}')
        return CreateCompanyAliasResponseSchema(company_alias=created)
    except Exception as e:
        logger.error(f'Error creating company alias: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create company alias: {str(e)}')


@company_aliases_router.post(
    '/bulk',
    status_code=201,
    response_model=CreateCompanyAliasesResponseSchema,
    summary='Create multiple new company aliases',
)
def create_company_aliases_bulk(
    request: Request,
    create_request: Annotated[CreateCompanyAliasesRequestSchema, Body()],
    service: CompanyAliasService = Depends(_get_write_company_alias_service),
) -> CreateCompanyAliasesResponseSchema:
    """Create multiple company aliases."""
    logger.info(f'Creating {len(create_request.company_aliases)} company aliases')

    try:
        created = service.create_company_aliases(create_request)
        logger.info(f'Successfully created {len(created)} company aliases')
        return CreateCompanyAliasesResponseSchema(company_aliases=created)
    except Exception as e:
        logger.error(f'Error creating company aliases in bulk: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create company aliases: {str(e)}')


@company_aliases_router.patch(
    '/{company_alias_id}',
    response_model=UpdateCompanyAliasResponseSchema,
    summary='Update a company alias',
)
def update_company_alias(
    request: Request,
    company_alias_id: str,
    update_request: Annotated[UpdateCompanyAliasRequestSchema, Body()],
    service: CompanyAliasService = Depends(_get_write_company_alias_service),
) -> UpdateCompanyAliasResponseSchema:
    """Update a company alias."""
    update_request.company_alias_id = company_alias_id
    logger.info(f'Updating company alias {company_alias_id}')

    try:
        updated = service.update_company_alias(update_request)
        logger.info(f'Company alias updated successfully: {updated.id}')
        return UpdateCompanyAliasResponseSchema(company_alias=updated)
    except ValueError as e:
        logger.warning(f'Company alias update failed - not found: {company_alias_id}')
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error updating company alias: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to update company alias: {str(e)}')


@company_aliases_router.get(
    '/{company_alias_id}',
    response_model=GetCompanyAliasByIdResponseSchema,
    summary='Get a company alias by its ID',
)
def get_company_alias_by_id(
    company_alias_id: str,
    service: CompanyAliasService = Depends(_get_company_alias_service),
) -> GetCompanyAliasByIdResponseSchema:
    """Get a company alias by ID."""
    logger.debug(f'Getting company alias {company_alias_id}')

    try:
        get_request = GetCompanyAliasByIdRequestSchema(company_alias_id=company_alias_id)
        company_alias = service.get_company_alias_by_id(get_request)
        if not company_alias:
            raise HTTPException(status_code=404, detail=f'Company alias with ID {company_alias_id} not found')
        return GetCompanyAliasByIdResponseSchema(company_alias=company_alias)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting company alias {company_alias_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to get company alias: {str(e)}')


@company_aliases_router.delete(
    '/{company_alias_id}',
    status_code=204,
    summary='Delete a company alias by its ID',
)
def delete_company_alias_by_id(
    company_alias_id: str,
    service: CompanyAliasService = Depends(_get_write_company_alias_service),
) -> None:
    """Delete a company alias by ID."""
    logger.info(f'Deleting company alias {company_alias_id}')

    try:
        delete_request = DeleteCompanyAliasByIdRequestSchema(company_alias_id=company_alias_id)
        service.delete_company_alias_by_id(delete_request)
        return Response(status_code=204)
    except ValueError as e:
        logger.warning(f'Company alias deletion failed - not found: {company_alias_id}')
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error deleting company alias {company_alias_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to delete company alias: {str(e)}')
