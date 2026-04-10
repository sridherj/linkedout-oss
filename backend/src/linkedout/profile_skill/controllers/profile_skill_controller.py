# SPDX-License-Identifier: Apache-2.0
"""Controller for ProfileSkill endpoints (shared, no tenant/BU scoping)."""
import math
from typing import Annotated, Generator

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, Response

from common.controllers.base_controller_utils import create_service_dependency
from common.schemas.base_response_schema import PaginationLinks
from linkedout.profile_skill.schemas.profile_skill_api_schema import (
    CreateProfileSkillRequestSchema,
    CreateProfileSkillResponseSchema,
    CreateProfileSkillsRequestSchema,
    CreateProfileSkillsResponseSchema,
    DeleteProfileSkillByIdRequestSchema,
    GetProfileSkillByIdRequestSchema,
    GetProfileSkillByIdResponseSchema,
    ListProfileSkillsRequestSchema,
    ListProfileSkillsResponseSchema,
    UpdateProfileSkillRequestSchema,
    UpdateProfileSkillResponseSchema,
)
from linkedout.profile_skill.services.profile_skill_service import ProfileSkillService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

profile_skills_router = APIRouter(
    prefix='/profile-skills',
    tags=['profile-skills'],
)

_META_FIELDS = ['sort_by', 'sort_order', 'crawled_profile_id', 'skill_name']


def _get_profile_skill_service(
    request: Request,
    app_user_id: str = Header(..., alias="X-App-User-Id"),
) -> Generator[ProfileSkillService, None, None]:
    yield from create_service_dependency(request, ProfileSkillService, DbSessionType.READ, app_user_id=app_user_id)


def _get_write_profile_skill_service(request: Request) -> Generator[ProfileSkillService, None, None]:
    yield from create_service_dependency(request, ProfileSkillService, DbSessionType.WRITE)


def _build_pagination_links(
    request: Request, total: int, limit: int, offset: int, params: dict,
) -> PaginationLinks:
    base_url = f'{request.url.scheme}://{request.url.netloc}/profile-skills'
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


@profile_skills_router.get(
    '', response_model=ListProfileSkillsResponseSchema,
    summary='List profile skills with filtering and pagination',
)
def list_profile_skills(
    request: Request,
    list_request: Annotated[ListProfileSkillsRequestSchema, Query()],
    service: ProfileSkillService = Depends(_get_profile_skill_service),
) -> ListProfileSkillsResponseSchema:
    logger.info('Listing profile skills')
    try:
        items, total_count = service.list_profile_skills(list_request)
        meta = {field: getattr(list_request, field, None) for field in _META_FIELDS}
        if total_count > 0:
            page_count = math.ceil(total_count / list_request.limit)
            links = _build_pagination_links(
                request=request, total=total_count,
                limit=list_request.limit, offset=list_request.offset, params=meta,
            )
            return ListProfileSkillsResponseSchema(
                profile_skills=items, total=total_count, limit=list_request.limit,
                offset=list_request.offset, page_count=page_count, links=links, meta=meta,
            )
        else:
            return ListProfileSkillsResponseSchema(
                profile_skills=[], total=0, limit=list_request.limit,
                offset=list_request.offset, page_count=1, links=None, meta=meta,
            )
    except Exception as e:
        logger.error(f'Error listing profile skills: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to list profile skills: {str(e)}')


@profile_skills_router.post(
    '', status_code=201, response_model=CreateProfileSkillResponseSchema,
    summary='Create a new profile skill',
)
def create_profile_skill(
    request: Request,
    create_request: Annotated[CreateProfileSkillRequestSchema, Body()],
    service: ProfileSkillService = Depends(_get_write_profile_skill_service),
) -> CreateProfileSkillResponseSchema:
    logger.info(f'Creating profile skill: {create_request.skill_name}')
    try:
        created = service.create_profile_skill(create_request)
        return CreateProfileSkillResponseSchema(profile_skill=created)
    except Exception as e:
        logger.error(f'Error creating profile skill: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create profile skill: {str(e)}')


@profile_skills_router.post(
    '/bulk', status_code=201, response_model=CreateProfileSkillsResponseSchema,
    summary='Create multiple profile skills',
)
def create_profile_skills_bulk(
    request: Request,
    create_request: Annotated[CreateProfileSkillsRequestSchema, Body()],
    service: ProfileSkillService = Depends(_get_write_profile_skill_service),
) -> CreateProfileSkillsResponseSchema:
    logger.info(f'Creating {len(create_request.profile_skills)} profile skills')
    try:
        created = service.create_profile_skills(create_request)
        return CreateProfileSkillsResponseSchema(profile_skills=created)
    except Exception as e:
        logger.error(f'Error creating profile skills in bulk: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create profile skills: {str(e)}')


@profile_skills_router.patch(
    '/{profile_skill_id}', response_model=UpdateProfileSkillResponseSchema,
    summary='Update a profile skill',
)
def update_profile_skill(
    request: Request,
    profile_skill_id: str,
    update_request: Annotated[UpdateProfileSkillRequestSchema, Body()],
    service: ProfileSkillService = Depends(_get_write_profile_skill_service),
) -> UpdateProfileSkillResponseSchema:
    update_request.profile_skill_id = profile_skill_id
    try:
        updated = service.update_profile_skill(update_request)
        return UpdateProfileSkillResponseSchema(profile_skill=updated)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error updating profile skill: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to update profile skill: {str(e)}')


@profile_skills_router.get(
    '/{profile_skill_id}', response_model=GetProfileSkillByIdResponseSchema,
    summary='Get a profile skill by its ID',
)
def get_profile_skill_by_id(
    profile_skill_id: str,
    service: ProfileSkillService = Depends(_get_profile_skill_service),
) -> GetProfileSkillByIdResponseSchema:
    try:
        req = GetProfileSkillByIdRequestSchema(profile_skill_id=profile_skill_id)
        result = service.get_profile_skill_by_id(req)
        if not result:
            raise HTTPException(status_code=404, detail=f'ProfileSkill with ID {profile_skill_id} not found')
        return GetProfileSkillByIdResponseSchema(profile_skill=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting profile skill {profile_skill_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to get profile skill: {str(e)}')


@profile_skills_router.delete(
    '/{profile_skill_id}', status_code=204,
    summary='Delete a profile skill by its ID',
)
def delete_profile_skill_by_id(
    profile_skill_id: str,
    service: ProfileSkillService = Depends(_get_write_profile_skill_service),
) -> None:
    try:
        req = DeleteProfileSkillByIdRequestSchema(profile_skill_id=profile_skill_id)
        service.delete_profile_skill_by_id(req)
        return Response(status_code=204)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error deleting profile skill {profile_skill_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to delete profile skill: {str(e)}')
