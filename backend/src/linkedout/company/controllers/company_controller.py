# SPDX-License-Identifier: Apache-2.0
"""Controller for Company endpoints (shared, no tenant/BU scoping)."""
import math
from typing import Annotated, Generator

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from common.controllers.base_controller_utils import create_service_dependency
from common.schemas.base_response_schema import PaginationLinks
from linkedout.company.schemas.company_api_schema import (
    CreateCompanyRequestSchema,
    CreateCompanyResponseSchema,
    CreateCompaniesRequestSchema,
    CreateCompaniesResponseSchema,
    DeleteCompanyByIdRequestSchema,
    GetCompanyByIdRequestSchema,
    GetCompanyByIdResponseSchema,
    ListCompaniesRequestSchema,
    ListCompaniesResponseSchema,
    UpdateCompanyRequestSchema,
    UpdateCompanyResponseSchema,
)
from linkedout.company.services.company_service import CompanyService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

companies_router = APIRouter(
    prefix='/companies',
    tags=['companies'],
)

_META_FIELDS = [
    'sort_by', 'sort_order', 'canonical_name', 'domain',
    'industry', 'size_tier', 'hq_country', 'company_ids',
]


def _get_company_service(request: Request) -> Generator[CompanyService, None, None]:
    yield from create_service_dependency(request, CompanyService, DbSessionType.READ)


def _get_write_company_service(request: Request) -> Generator[CompanyService, None, None]:
    yield from create_service_dependency(request, CompanyService, DbSessionType.WRITE)


def _build_pagination_links(
    request: Request,
    total: int,
    limit: int,
    offset: int,
    params: dict,
) -> PaginationLinks:
    """Build HATEOAS pagination links for companies."""
    base_url = f'{request.url.scheme}://{request.url.netloc}/companies'

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


@companies_router.get(
    '',
    response_model=ListCompaniesResponseSchema,
    summary='List companies with filtering and pagination',
)
def list_companies(
    request: Request,
    list_request: Annotated[ListCompaniesRequestSchema, Query()],
    service: CompanyService = Depends(_get_company_service),
) -> ListCompaniesResponseSchema:
    """List companies with filters."""
    logger.info('Listing companies')

    try:
        companies, total_count = service.list_companies(list_request)

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
            return ListCompaniesResponseSchema(
                companies=companies,
                total=total_count,
                limit=list_request.limit,
                offset=list_request.offset,
                page_count=page_count,
                links=links,
                meta=meta,
            )
        else:
            return ListCompaniesResponseSchema(
                companies=[],
                total=0,
                limit=list_request.limit,
                offset=list_request.offset,
                page_count=1,
                links=None,
                meta=meta,
            )
    except Exception as e:
        logger.error(f'Error listing companies: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to list companies: {str(e)}')


@companies_router.post(
    '',
    status_code=201,
    response_model=CreateCompanyResponseSchema,
    summary='Create a new company',
)
def create_company(
    request: Request,
    create_request: Annotated[CreateCompanyRequestSchema, Body()],
    service: CompanyService = Depends(_get_write_company_service),
) -> CreateCompanyResponseSchema:
    """Create a new company."""
    logger.info(f'Creating company: {create_request.canonical_name}')

    try:
        created = service.create_company(create_request)
        logger.info(f'Company created successfully: {created.id}')
        return CreateCompanyResponseSchema(company=created)
    except Exception as e:
        logger.error(f'Error creating company: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create company: {str(e)}')


@companies_router.post(
    '/bulk',
    status_code=201,
    response_model=CreateCompaniesResponseSchema,
    summary='Create multiple new companies',
)
def create_companies_bulk(
    request: Request,
    create_request: Annotated[CreateCompaniesRequestSchema, Body()],
    service: CompanyService = Depends(_get_write_company_service),
) -> CreateCompaniesResponseSchema:
    """Create multiple companies."""
    logger.info(f'Creating {len(create_request.companies)} companies')

    try:
        created = service.create_companies(create_request)
        logger.info(f'Successfully created {len(created)} companies')
        return CreateCompaniesResponseSchema(companies=created)
    except Exception as e:
        logger.error(f'Error creating companies in bulk: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create companies: {str(e)}')


@companies_router.patch(
    '/{company_id}',
    response_model=UpdateCompanyResponseSchema,
    summary='Update a company',
)
def update_company(
    request: Request,
    company_id: str,
    update_request: Annotated[UpdateCompanyRequestSchema, Body()],
    service: CompanyService = Depends(_get_write_company_service),
) -> UpdateCompanyResponseSchema:
    """Update a company."""
    update_request.company_id = company_id
    logger.info(f'Updating company {company_id}')

    try:
        updated = service.update_company(update_request)
        logger.info(f'Company updated successfully: {updated.id}')
        return UpdateCompanyResponseSchema(company=updated)
    except ValueError as e:
        logger.warning(f'Company update failed - not found: {company_id}')
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error updating company: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to update company: {str(e)}')


@companies_router.get(
    '/{company_id}',
    response_model=GetCompanyByIdResponseSchema,
    summary='Get a company by its ID',
)
def get_company_by_id(
    company_id: str,
    service: CompanyService = Depends(_get_company_service),
) -> GetCompanyByIdResponseSchema:
    """Get a company by ID."""
    logger.debug(f'Getting company {company_id}')

    try:
        get_request = GetCompanyByIdRequestSchema(company_id=company_id)
        company = service.get_company_by_id(get_request)
        if not company:
            raise HTTPException(status_code=404, detail=f'Company with ID {company_id} not found')
        return GetCompanyByIdResponseSchema(company=company)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting company {company_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to get company: {str(e)}')


@companies_router.delete(
    '/{company_id}',
    status_code=204,
    summary='Delete a company by its ID',
)
def delete_company_by_id(
    company_id: str,
    service: CompanyService = Depends(_get_write_company_service),
) -> None:
    """Delete a company by ID."""
    logger.info(f'Deleting company {company_id}')

    try:
        delete_request = DeleteCompanyByIdRequestSchema(company_id=company_id)
        service.delete_company_by_id(delete_request)
        return Response(status_code=204)
    except ValueError as e:
        logger.warning(f'Company deletion failed - not found: {company_id}')
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error deleting company {company_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to delete company: {str(e)}')
