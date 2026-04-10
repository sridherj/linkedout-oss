# SPDX-License-Identifier: Apache-2.0
"""Controller for CrawledProfile endpoints (shared, no tenant/BU scoping)."""
import math
from typing import Annotated, Generator

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, Response

from common.controllers.base_controller_utils import create_service_dependency
from common.schemas.base_response_schema import PaginationLinks
from linkedout.crawled_profile.schemas.crawled_profile_api_schema import (
    CreateCrawledProfileRequestSchema,
    CreateCrawledProfileResponseSchema,
    CreateCrawledProfilesRequestSchema,
    CreateCrawledProfilesResponseSchema,
    DeleteCrawledProfileByIdRequestSchema,
    EnrichProfileRequestSchema,
    EnrichProfileResponseSchema,
    GetCrawledProfileByIdRequestSchema,
    GetCrawledProfileByIdResponseSchema,
    ListCrawledProfilesRequestSchema,
    ListCrawledProfilesResponseSchema,
    UpdateCrawledProfileRequestSchema,
    UpdateCrawledProfileResponseSchema,
)
from linkedout.crawled_profile.services.crawled_profile_service import CrawledProfileService
from linkedout.crawled_profile.services.profile_enrichment_service import ProfileEnrichmentService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger
from utilities.llm_manager.embedding_factory import get_embedding_provider

logger = get_logger(__name__)

crawled_profiles_router = APIRouter(
    prefix='/crawled-profiles',
    tags=['crawled-profiles'],
)

_META_FIELDS = [
    'sort_by', 'sort_order', 'full_name', 'current_company_name',
    'company_id', 'seniority_level', 'function_area', 'data_source',
    'has_enriched_data', 'location_country_code', 'crawled_profile_ids',
    'linkedin_url',
]


def _get_crawled_profile_service(
    request: Request,
    app_user_id: str = Header(..., alias="X-App-User-Id"),
) -> Generator[CrawledProfileService, None, None]:
    yield from create_service_dependency(request, CrawledProfileService, DbSessionType.READ, app_user_id=app_user_id)


def _get_write_crawled_profile_service(
    request: Request,
    app_user_id: str = Header(..., alias="X-App-User-Id"),
) -> Generator[CrawledProfileService, None, None]:
    yield from create_service_dependency(request, CrawledProfileService, DbSessionType.WRITE, app_user_id=app_user_id)


def _get_enrichment_service(
    request: Request,
    app_user_id: str = Header(..., alias="X-App-User-Id"),
) -> Generator[ProfileEnrichmentService, None, None]:
    db_manager = request.app.state.db_manager
    with db_manager.get_session(DbSessionType.WRITE, app_user_id=app_user_id) as session:
        try:
            embedding_provider = get_embedding_provider()
        except Exception:
            embedding_provider = None
        yield ProfileEnrichmentService(session, embedding_provider)


def _build_pagination_links(
    request: Request,
    total: int,
    limit: int,
    offset: int,
    params: dict,
) -> PaginationLinks:
    """Build HATEOAS pagination links for crawled profiles."""
    base_url = f'{request.url.scheme}://{request.url.netloc}/crawled-profiles'

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


@crawled_profiles_router.get(
    '',
    response_model=ListCrawledProfilesResponseSchema,
    summary='List crawled profiles with filtering and pagination',
)
def list_crawled_profiles(
    request: Request,
    list_request: Annotated[ListCrawledProfilesRequestSchema, Query()],
    service: CrawledProfileService = Depends(_get_crawled_profile_service),
) -> ListCrawledProfilesResponseSchema:
    """List crawled profiles with filters."""
    logger.info('Listing crawled profiles')

    try:
        crawled_profiles, total_count = service.list_crawled_profiles(list_request)

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
            return ListCrawledProfilesResponseSchema(
                crawled_profiles=crawled_profiles,
                total=total_count,
                limit=list_request.limit,
                offset=list_request.offset,
                page_count=page_count,
                links=links,
                meta=meta,
            )
        else:
            return ListCrawledProfilesResponseSchema(
                crawled_profiles=[],
                total=0,
                limit=list_request.limit,
                offset=list_request.offset,
                page_count=1,
                links=None,
                meta=meta,
            )
    except Exception as e:
        logger.error(f'Error listing crawled profiles: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to list crawled profiles: {str(e)}')


@crawled_profiles_router.post(
    '',
    status_code=201,
    response_model=CreateCrawledProfileResponseSchema,
    summary='Create a new crawled profile',
)
def create_crawled_profile(
    request: Request,
    create_request: Annotated[CreateCrawledProfileRequestSchema, Body()],
    service: CrawledProfileService = Depends(_get_write_crawled_profile_service),
) -> CreateCrawledProfileResponseSchema:
    """Create a new crawled profile."""
    logger.info(f'Creating crawled profile: {create_request.linkedin_url}')

    try:
        created = service.create_crawled_profile(create_request)
        logger.info(f'CrawledProfile created successfully: {created.id}')
        return CreateCrawledProfileResponseSchema(crawled_profile=created)
    except Exception as e:
        logger.error(f'Error creating crawled profile: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create crawled profile: {str(e)}')


@crawled_profiles_router.post(
    '/bulk',
    status_code=201,
    response_model=CreateCrawledProfilesResponseSchema,
    summary='Create multiple new crawled profiles',
)
def create_crawled_profiles_bulk(
    request: Request,
    create_request: Annotated[CreateCrawledProfilesRequestSchema, Body()],
    service: CrawledProfileService = Depends(_get_write_crawled_profile_service),
) -> CreateCrawledProfilesResponseSchema:
    """Create multiple crawled profiles."""
    logger.info(f'Creating {len(create_request.crawled_profiles)} crawled profiles')

    try:
        created = service.create_crawled_profiles(create_request)
        logger.info(f'Successfully created {len(created)} crawled profiles')
        return CreateCrawledProfilesResponseSchema(crawled_profiles=created)
    except Exception as e:
        logger.error(f'Error creating crawled profiles in bulk: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create crawled profiles: {str(e)}')


@crawled_profiles_router.patch(
    '/{crawled_profile_id}',
    response_model=UpdateCrawledProfileResponseSchema,
    summary='Update a crawled profile',
)
def update_crawled_profile(
    request: Request,
    crawled_profile_id: str,
    update_request: Annotated[UpdateCrawledProfileRequestSchema, Body()],
    service: CrawledProfileService = Depends(_get_write_crawled_profile_service),
) -> UpdateCrawledProfileResponseSchema:
    """Update a crawled profile."""
    update_request.crawled_profile_id = crawled_profile_id
    logger.info(f'Updating crawled profile {crawled_profile_id}')

    try:
        updated = service.update_crawled_profile(update_request)
        logger.info(f'CrawledProfile updated successfully: {updated.id}')
        return UpdateCrawledProfileResponseSchema(crawled_profile=updated)
    except ValueError as e:
        logger.warning(f'CrawledProfile update failed - not found: {crawled_profile_id}')
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error updating crawled profile: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to update crawled profile: {str(e)}')


@crawled_profiles_router.get(
    '/{crawled_profile_id}',
    response_model=GetCrawledProfileByIdResponseSchema,
    summary='Get a crawled profile by its ID',
)
def get_crawled_profile_by_id(
    crawled_profile_id: str,
    service: CrawledProfileService = Depends(_get_crawled_profile_service),
) -> GetCrawledProfileByIdResponseSchema:
    """Get a crawled profile by ID."""
    logger.debug(f'Getting crawled profile {crawled_profile_id}')

    try:
        get_request = GetCrawledProfileByIdRequestSchema(crawled_profile_id=crawled_profile_id)
        crawled_profile = service.get_crawled_profile_by_id(get_request)
        if not crawled_profile:
            raise HTTPException(status_code=404, detail=f'CrawledProfile with ID {crawled_profile_id} not found')
        return GetCrawledProfileByIdResponseSchema(crawled_profile=crawled_profile)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting crawled profile {crawled_profile_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to get crawled profile: {str(e)}')


@crawled_profiles_router.delete(
    '/{crawled_profile_id}',
    status_code=204,
    summary='Delete a crawled profile by its ID',
)
def delete_crawled_profile_by_id(
    crawled_profile_id: str,
    service: CrawledProfileService = Depends(_get_write_crawled_profile_service),
) -> None:
    """Delete a crawled profile by ID."""
    logger.info(f'Deleting crawled profile {crawled_profile_id}')

    try:
        delete_request = DeleteCrawledProfileByIdRequestSchema(crawled_profile_id=crawled_profile_id)
        service.delete_crawled_profile_by_id(delete_request)
        return Response(status_code=204)
    except ValueError as e:
        logger.warning(f'CrawledProfile deletion failed - not found: {crawled_profile_id}')
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error deleting crawled profile {crawled_profile_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to delete crawled profile: {str(e)}')


@crawled_profiles_router.post(
    '/{crawled_profile_id}/enrich',
    response_model=EnrichProfileResponseSchema,
    summary='Enrich a profile with experience, education, and skill data',
)
def enrich_crawled_profile(
    crawled_profile_id: str,
    enrich_request: Annotated[EnrichProfileRequestSchema, Body()],
    service: ProfileEnrichmentService = Depends(_get_enrichment_service),
) -> EnrichProfileResponseSchema:
    """Enrich a crawled profile with structured experience, education, and skill data."""
    logger.info(f'Enriching crawled profile {crawled_profile_id}')

    try:
        result = service.enrich(crawled_profile_id, enrich_request)
        logger.info(f'CrawledProfile enriched successfully: {crawled_profile_id}')
        return result
    except ValueError as e:
        logger.warning(f'CrawledProfile enrichment failed - not found: {crawled_profile_id}')
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error enriching crawled profile {crawled_profile_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to enrich crawled profile: {str(e)}')
