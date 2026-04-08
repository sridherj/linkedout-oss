# SPDX-License-Identifier: Apache-2.0
"""Service for ProfileSkill entity (shared, no tenant/BU scoping)."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from linkedout.profile_skill.entities.profile_skill_entity import ProfileSkillEntity
from linkedout.profile_skill.repositories.profile_skill_repository import ProfileSkillRepository
from linkedout.profile_skill.schemas.profile_skill_api_schema import (
    CreateProfileSkillRequestSchema,
    CreateProfileSkillsRequestSchema,
    DeleteProfileSkillByIdRequestSchema,
    GetProfileSkillByIdRequestSchema,
    ListProfileSkillsRequestSchema,
    UpdateProfileSkillRequestSchema,
)
from linkedout.profile_skill.schemas.profile_skill_schema import ProfileSkillSchema
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class ProfileSkillService:
    def __init__(self, session: Session):
        self._session = session
        self._repository = ProfileSkillRepository(session)
        logger.debug('Initialized ProfileSkillService')

    def list_profile_skills(
        self, list_request: ListProfileSkillsRequestSchema
    ) -> Tuple[List[ProfileSkillSchema], int]:
        logger.debug('Listing profile skills')
        items = self._repository.list_with_filters(
            limit=list_request.limit,
            offset=list_request.offset,
            sort_by=list_request.sort_by,
            sort_order=list_request.sort_order,
            crawled_profile_id=list_request.crawled_profile_id,
            skill_name=list_request.skill_name,
        )
        total = self._repository.count_with_filters(
            crawled_profile_id=list_request.crawled_profile_id,
            skill_name=list_request.skill_name,
        )
        return [ProfileSkillSchema.model_validate(e) for e in items], total

    def create_profile_skill(self, req: CreateProfileSkillRequestSchema) -> ProfileSkillSchema:
        entity = ProfileSkillEntity(
            crawled_profile_id=req.crawled_profile_id,
            skill_name=req.skill_name,
            endorsement_count=req.endorsement_count,
        )
        created = self._repository.create(entity)
        return ProfileSkillSchema.model_validate(created)

    def create_profile_skills(self, req: CreateProfileSkillsRequestSchema) -> List[ProfileSkillSchema]:
        results = []
        for item in req.profile_skills:
            entity = ProfileSkillEntity(
                crawled_profile_id=item.crawled_profile_id,
                skill_name=item.skill_name,
                endorsement_count=item.endorsement_count,
            )
            created = self._repository.create(entity)
            results.append(created)
        return [ProfileSkillSchema.model_validate(e) for e in results]

    def update_profile_skill(self, req: UpdateProfileSkillRequestSchema) -> ProfileSkillSchema:
        assert req.profile_skill_id is not None
        entity = self._repository.get_by_id(req.profile_skill_id)
        if not entity:
            raise ValueError(f'ProfileSkill not found with ID: {req.profile_skill_id}')
        if req.skill_name is not None:
            entity.skill_name = req.skill_name
        if req.endorsement_count is not None:
            entity.endorsement_count = req.endorsement_count
        updated = self._repository.update(entity)
        return ProfileSkillSchema.model_validate(updated)

    def get_profile_skill_by_id(self, req: GetProfileSkillByIdRequestSchema) -> Optional[ProfileSkillSchema]:
        assert req.profile_skill_id is not None
        entity = self._repository.get_by_id(req.profile_skill_id)
        if not entity:
            return None
        return ProfileSkillSchema.model_validate(entity)

    def delete_profile_skill_by_id(self, req: DeleteProfileSkillByIdRequestSchema) -> None:
        assert req.profile_skill_id is not None
        entity = self._repository.get_by_id(req.profile_skill_id)
        if not entity:
            raise ValueError(f'ProfileSkill not found with ID: {req.profile_skill_id}')
        self._repository.delete(entity)
