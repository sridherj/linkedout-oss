# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for ProfileSkill API."""
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.profile_skill.schemas.profile_skill_schema import ProfileSkillSchema


class ProfileSkillSortByFields(StrEnum):
    CREATED_AT = 'created_at'
    SKILL_NAME = 'skill_name'
    ENDORSEMENT_COUNT = 'endorsement_count'


class ListProfileSkillsRequestSchema(PaginateRequestSchema):
    sort_by: Annotated[ProfileSkillSortByFields, Field(description='Sort field', default=ProfileSkillSortByFields.CREATED_AT)] = ProfileSkillSortByFields.CREATED_AT
    sort_order: Annotated[SortOrder, Field(description='Sort order', default=SortOrder.ASC)] = SortOrder.ASC
    crawled_profile_id: Annotated[Optional[str], Field(description='Filter by profile', default=None)] = None
    skill_name: Annotated[Optional[str], Field(description='Filter by skill name', default=None)] = None


class CreateProfileSkillRequestSchema(BaseRequestSchema):
    crawled_profile_id: Annotated[str, Field(description='Profile this skill belongs to')]
    skill_name: Annotated[str, Field(description='Name of the skill')]
    endorsement_count: Annotated[int, Field(description='Number of endorsements', default=0)] = 0


class CreateProfileSkillsRequestSchema(BaseRequestSchema):
    profile_skills: List[CreateProfileSkillRequestSchema]


class UpdateProfileSkillRequestSchema(BaseRequestSchema):
    profile_skill_id: Annotated[Optional[str], Field(description='Skill ID to update', default=None)] = None
    skill_name: Annotated[Optional[str], Field(description='Name of the skill', default=None)] = None
    endorsement_count: Annotated[Optional[int], Field(description='Number of endorsements', default=None)] = None


class GetProfileSkillByIdRequestSchema(BaseRequestSchema):
    profile_skill_id: Optional[str] = None


class DeleteProfileSkillByIdRequestSchema(BaseRequestSchema):
    profile_skill_id: Optional[str] = None


class ListProfileSkillsResponseSchema(PaginateResponseSchema):
    profile_skills: List[ProfileSkillSchema]


class CreateProfileSkillResponseSchema(BaseResponseSchema):
    profile_skill: ProfileSkillSchema


class CreateProfileSkillsResponseSchema(BaseResponseSchema):
    profile_skills: List[ProfileSkillSchema]


class UpdateProfileSkillResponseSchema(BaseResponseSchema):
    profile_skill: ProfileSkillSchema


class GetProfileSkillByIdResponseSchema(BaseResponseSchema):
    profile_skill: ProfileSkillSchema
