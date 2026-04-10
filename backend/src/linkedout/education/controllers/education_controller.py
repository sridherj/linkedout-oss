# SPDX-License-Identifier: Apache-2.0
"""Controller for Education endpoints (shared, no tenant/BU scoping)."""
import math
from typing import Annotated, Generator

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, Response

from common.controllers.base_controller_utils import create_service_dependency
from common.schemas.base_response_schema import PaginationLinks
from linkedout.education.schemas.education_api_schema import (
    CreateEducationRequestSchema,
    CreateEducationResponseSchema,
    CreateEducationsRequestSchema,
    CreateEducationsResponseSchema,
    DeleteEducationByIdRequestSchema,
    GetEducationByIdRequestSchema,
    GetEducationByIdResponseSchema,
    ListEducationsRequestSchema,
    ListEducationsResponseSchema,
    UpdateEducationRequestSchema,
    UpdateEducationResponseSchema,
)
from linkedout.education.services.education_service import EducationService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

educations_router = APIRouter(
    prefix='/educations',
    tags=['educations'],
)

_META_FIELDS = [
    'sort_by', 'sort_order', 'crawled_profile_id', 'school_name', 'degree',
]


def _get_education_service(
    request: Request,
    app_user_id: str = Header(..., alias="X-App-User-Id"),
) -> Generator[EducationService, None, None]:
    yield from create_service_dependency(request, EducationService, DbSessionType.READ, app_user_id=app_user_id)


def _get_write_education_service(request: Request) -> Generator[EducationService, None, None]:
    yield from create_service_dependency(request, EducationService, DbSessionType.WRITE)


def _build_pagination_links(
    request: Request,
    total: int,
    limit: int,
    offset: int,
    params: dict,
) -> PaginationLinks:
    """Build HATEOAS pagination links for educations."""
    base_url = f'{request.url.scheme}://{request.url.netloc}/educations'

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


@educations_router.get(
    '',
    response_model=ListEducationsResponseSchema,
    summary='List educations with filtering and pagination',
)
def list_educations(
    request: Request,
    list_request: Annotated[ListEducationsRequestSchema, Query()],
    service: EducationService = Depends(_get_education_service),
) -> ListEducationsResponseSchema:
    """List educations with filters."""
    logger.info('Listing educations')

    try:
        educations, total_count = service.list_educations(list_request)

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
            return ListEducationsResponseSchema(
                educations=educations,
                total=total_count,
                limit=list_request.limit,
                offset=list_request.offset,
                page_count=page_count,
                links=links,
                meta=meta,
            )
        else:
            return ListEducationsResponseSchema(
                educations=[],
                total=0,
                limit=list_request.limit,
                offset=list_request.offset,
                page_count=1,
                links=None,
                meta=meta,
            )
    except Exception as e:
        logger.error(f'Error listing educations: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to list educations: {str(e)}')


@educations_router.post(
    '',
    status_code=201,
    response_model=CreateEducationResponseSchema,
    summary='Create a new education',
)
def create_education(
    request: Request,
    create_request: Annotated[CreateEducationRequestSchema, Body()],
    service: EducationService = Depends(_get_write_education_service),
) -> CreateEducationResponseSchema:
    """Create a new education."""
    logger.info(f'Creating education for profile: {create_request.crawled_profile_id}')

    try:
        created = service.create_education(create_request)
        logger.info(f'Education created successfully: {created.id}')
        return CreateEducationResponseSchema(education=created)
    except Exception as e:
        logger.error(f'Error creating education: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create education: {str(e)}')


@educations_router.post(
    '/bulk',
    status_code=201,
    response_model=CreateEducationsResponseSchema,
    summary='Create multiple new educations',
)
def create_educations_bulk(
    request: Request,
    create_request: Annotated[CreateEducationsRequestSchema, Body()],
    service: EducationService = Depends(_get_write_education_service),
) -> CreateEducationsResponseSchema:
    """Create multiple educations."""
    logger.info(f'Creating {len(create_request.educations)} educations')

    try:
        created = service.create_educations(create_request)
        logger.info(f'Successfully created {len(created)} educations')
        return CreateEducationsResponseSchema(educations=created)
    except Exception as e:
        logger.error(f'Error creating educations in bulk: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create educations: {str(e)}')


@educations_router.patch(
    '/{education_id}',
    response_model=UpdateEducationResponseSchema,
    summary='Update an education',
)
def update_education(
    request: Request,
    education_id: str,
    update_request: Annotated[UpdateEducationRequestSchema, Body()],
    service: EducationService = Depends(_get_write_education_service),
) -> UpdateEducationResponseSchema:
    """Update an education."""
    update_request.education_id = education_id
    logger.info(f'Updating education {education_id}')

    try:
        updated = service.update_education(update_request)
        logger.info(f'Education updated successfully: {updated.id}')
        return UpdateEducationResponseSchema(education=updated)
    except ValueError as e:
        logger.warning(f'Education update failed - not found: {education_id}')
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error updating education: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to update education: {str(e)}')


@educations_router.get(
    '/{education_id}',
    response_model=GetEducationByIdResponseSchema,
    summary='Get an education by its ID',
)
def get_education_by_id(
    education_id: str,
    service: EducationService = Depends(_get_education_service),
) -> GetEducationByIdResponseSchema:
    """Get an education by ID."""
    logger.debug(f'Getting education {education_id}')

    try:
        get_request = GetEducationByIdRequestSchema(education_id=education_id)
        education = service.get_education_by_id(get_request)
        if not education:
            raise HTTPException(status_code=404, detail=f'Education with ID {education_id} not found')
        return GetEducationByIdResponseSchema(education=education)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting education {education_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to get education: {str(e)}')


@educations_router.delete(
    '/{education_id}',
    status_code=204,
    summary='Delete an education by its ID',
)
def delete_education_by_id(
    education_id: str,
    service: EducationService = Depends(_get_write_education_service),
) -> None:
    """Delete an education by ID."""
    logger.info(f'Deleting education {education_id}')

    try:
        delete_request = DeleteEducationByIdRequestSchema(education_id=education_id)
        service.delete_education_by_id(delete_request)
        return Response(status_code=204)
    except ValueError as e:
        logger.warning(f'Education deletion failed - not found: {education_id}')
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error deleting education {education_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to delete education: {str(e)}')
