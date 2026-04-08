# SPDX-License-Identifier: Apache-2.0
"""Controller for Experience endpoints (shared, no tenant/BU scoping)."""
import math
from typing import Annotated, Generator

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, Response

from common.controllers.base_controller_utils import create_service_dependency
from common.schemas.base_response_schema import PaginationLinks
from linkedout.experience.schemas.experience_api_schema import (
    CreateExperienceRequestSchema,
    CreateExperienceResponseSchema,
    CreateExperiencesRequestSchema,
    CreateExperiencesResponseSchema,
    DeleteExperienceByIdRequestSchema,
    GetExperienceByIdRequestSchema,
    GetExperienceByIdResponseSchema,
    ListExperiencesRequestSchema,
    ListExperiencesResponseSchema,
    UpdateExperienceRequestSchema,
    UpdateExperienceResponseSchema,
)
from linkedout.experience.services.experience_service import ExperienceService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

experiences_router = APIRouter(
    prefix='/experiences',
    tags=['experiences'],
)

_META_FIELDS = [
    'sort_by', 'sort_order', 'crawled_profile_id', 'company_id',
    'is_current', 'employment_type',
]


def _get_experience_service(
    app_user_id: str = Header(..., alias="X-App-User-Id"),
) -> Generator[ExperienceService, None, None]:
    yield from create_service_dependency(ExperienceService, DbSessionType.READ, app_user_id=app_user_id)


def _get_write_experience_service() -> Generator[ExperienceService, None, None]:
    yield from create_service_dependency(ExperienceService, DbSessionType.WRITE)


def _build_pagination_links(
    request: Request,
    total: int,
    limit: int,
    offset: int,
    params: dict,
) -> PaginationLinks:
    """Build HATEOAS pagination links for experiences."""
    base_url = f'{request.url.scheme}://{request.url.netloc}/experiences'

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


@experiences_router.get(
    '',
    response_model=ListExperiencesResponseSchema,
    summary='List experiences with filtering and pagination',
)
def list_experiences(
    request: Request,
    list_request: Annotated[ListExperiencesRequestSchema, Query()],
    service: ExperienceService = Depends(_get_experience_service),
) -> ListExperiencesResponseSchema:
    """List experiences with filters."""
    logger.info('Listing experiences')

    try:
        experiences, total_count = service.list_experiences(list_request)

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
            return ListExperiencesResponseSchema(
                experiences=experiences,
                total=total_count,
                limit=list_request.limit,
                offset=list_request.offset,
                page_count=page_count,
                links=links,
                meta=meta,
            )
        else:
            return ListExperiencesResponseSchema(
                experiences=[],
                total=0,
                limit=list_request.limit,
                offset=list_request.offset,
                page_count=1,
                links=None,
                meta=meta,
            )
    except Exception as e:
        logger.error(f'Error listing experiences: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to list experiences: {str(e)}')


@experiences_router.post(
    '',
    status_code=201,
    response_model=CreateExperienceResponseSchema,
    summary='Create a new experience',
)
def create_experience(
    request: Request,
    create_request: Annotated[CreateExperienceRequestSchema, Body()],
    service: ExperienceService = Depends(_get_write_experience_service),
) -> CreateExperienceResponseSchema:
    """Create a new experience."""
    logger.info(f'Creating experience for profile: {create_request.crawled_profile_id}')

    try:
        created = service.create_experience(create_request)
        logger.info(f'Experience created successfully: {created.id}')
        return CreateExperienceResponseSchema(experience=created)
    except Exception as e:
        logger.error(f'Error creating experience: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create experience: {str(e)}')


@experiences_router.post(
    '/bulk',
    status_code=201,
    response_model=CreateExperiencesResponseSchema,
    summary='Create multiple new experiences',
)
def create_experiences_bulk(
    request: Request,
    create_request: Annotated[CreateExperiencesRequestSchema, Body()],
    service: ExperienceService = Depends(_get_write_experience_service),
) -> CreateExperiencesResponseSchema:
    """Create multiple experiences."""
    logger.info(f'Creating {len(create_request.experiences)} experiences')

    try:
        created = service.create_experiences(create_request)
        logger.info(f'Successfully created {len(created)} experiences')
        return CreateExperiencesResponseSchema(experiences=created)
    except Exception as e:
        logger.error(f'Error creating experiences in bulk: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create experiences: {str(e)}')


@experiences_router.patch(
    '/{experience_id}',
    response_model=UpdateExperienceResponseSchema,
    summary='Update an experience',
)
def update_experience(
    request: Request,
    experience_id: str,
    update_request: Annotated[UpdateExperienceRequestSchema, Body()],
    service: ExperienceService = Depends(_get_write_experience_service),
) -> UpdateExperienceResponseSchema:
    """Update an experience."""
    update_request.experience_id = experience_id
    logger.info(f'Updating experience {experience_id}')

    try:
        updated = service.update_experience(update_request)
        logger.info(f'Experience updated successfully: {updated.id}')
        return UpdateExperienceResponseSchema(experience=updated)
    except ValueError as e:
        logger.warning(f'Experience update failed - not found: {experience_id}')
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error updating experience: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to update experience: {str(e)}')


@experiences_router.get(
    '/{experience_id}',
    response_model=GetExperienceByIdResponseSchema,
    summary='Get an experience by its ID',
)
def get_experience_by_id(
    experience_id: str,
    service: ExperienceService = Depends(_get_experience_service),
) -> GetExperienceByIdResponseSchema:
    """Get an experience by ID."""
    logger.debug(f'Getting experience {experience_id}')

    try:
        get_request = GetExperienceByIdRequestSchema(experience_id=experience_id)
        experience = service.get_experience_by_id(get_request)
        if not experience:
            raise HTTPException(status_code=404, detail=f'Experience with ID {experience_id} not found')
        return GetExperienceByIdResponseSchema(experience=experience)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting experience {experience_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to get experience: {str(e)}')


@experiences_router.delete(
    '/{experience_id}',
    status_code=204,
    summary='Delete an experience by its ID',
)
def delete_experience_by_id(
    experience_id: str,
    service: ExperienceService = Depends(_get_write_experience_service),
) -> None:
    """Delete an experience by ID."""
    logger.info(f'Deleting experience {experience_id}')

    try:
        delete_request = DeleteExperienceByIdRequestSchema(experience_id=experience_id)
        service.delete_experience_by_id(delete_request)
        return Response(status_code=204)
    except ValueError as e:
        logger.warning(f'Experience deletion failed - not found: {experience_id}')
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error deleting experience {experience_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to delete experience: {str(e)}')
