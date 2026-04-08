# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for Experience API."""
from datetime import date
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.experience.schemas.experience_schema import ExperienceSchema


class ExperienceSortByFields(StrEnum):
    CREATED_AT = 'created_at'
    START_DATE = 'start_date'
    POSITION = 'position'


class ListExperiencesRequestSchema(PaginateRequestSchema):
    sort_by: Annotated[ExperienceSortByFields, Field(description='Sort field', default=ExperienceSortByFields.CREATED_AT)] = ExperienceSortByFields.CREATED_AT
    sort_order: Annotated[SortOrder, Field(description='Sort order', default=SortOrder.ASC)] = SortOrder.ASC
    crawled_profile_id: Annotated[Optional[str], Field(description='Filter by profile', default=None)] = None
    company_id: Annotated[Optional[str], Field(description='Filter by company', default=None)] = None
    is_current: Annotated[Optional[bool], Field(description='Filter by current role status', default=None)] = None
    employment_type: Annotated[Optional[str], Field(description='Filter by employment type', default=None)] = None


class CreateExperienceRequestSchema(BaseRequestSchema):
    crawled_profile_id: Annotated[str, Field(description='Profile this experience belongs to')]
    position: Annotated[Optional[str], Field(description='Job title or position', default=None)] = None
    position_normalized: Annotated[Optional[str], Field(description='Normalized job title', default=None)] = None
    company_name: Annotated[Optional[str], Field(description='Name of the company', default=None)] = None
    company_id: Annotated[Optional[str], Field(description='Resolved company entity ID if matched', default=None)] = None
    company_linkedin_url: Annotated[Optional[str], Field(description='LinkedIn URL of the company', default=None)] = None
    employment_type: Annotated[Optional[str], Field(description='Type of employment (full-time, part-time, etc)', default=None)] = None
    start_date: Annotated[Optional[date], Field(description='Start date of role', default=None)] = None
    start_year: Annotated[Optional[int], Field(description='Start year', default=None)] = None
    start_month: Annotated[Optional[int], Field(description='Start month', default=None)] = None
    end_date: Annotated[Optional[date], Field(description='End date of role', default=None)] = None
    end_year: Annotated[Optional[int], Field(description='End year', default=None)] = None
    end_month: Annotated[Optional[int], Field(description='End month', default=None)] = None
    end_date_text: Annotated[Optional[str], Field(description='Textual end date like "Present"', default=None)] = None
    seniority_level: Annotated[Optional[str], Field(description='Estimated seniority level', default=None)] = None
    function_area: Annotated[Optional[str], Field(description='Function area or department', default=None)] = None
    location: Annotated[Optional[str], Field(description='Location of the role', default=None)] = None
    description: Annotated[Optional[str], Field(description='Description of the role/experience', default=None)] = None
    raw_experience: Annotated[Optional[str], Field(description='Raw JSON payload of experience data', default=None)] = None


class CreateExperiencesRequestSchema(BaseRequestSchema):
    experiences: List[CreateExperienceRequestSchema]


class UpdateExperienceRequestSchema(BaseRequestSchema):
    experience_id: Annotated[Optional[str], Field(description='Experience ID to update', default=None)] = None
    position: Annotated[Optional[str], Field(description='Job title or position', default=None)] = None
    position_normalized: Annotated[Optional[str], Field(description='Normalized job title', default=None)] = None
    company_name: Annotated[Optional[str], Field(description='Name of the company', default=None)] = None
    company_id: Annotated[Optional[str], Field(description='Resolved company entity ID if matched', default=None)] = None
    company_linkedin_url: Annotated[Optional[str], Field(description='LinkedIn URL of the company', default=None)] = None
    employment_type: Annotated[Optional[str], Field(description='Type of employment (full-time, part-time, etc)', default=None)] = None
    start_date: Annotated[Optional[date], Field(description='Start date of role', default=None)] = None
    start_year: Annotated[Optional[int], Field(description='Start year', default=None)] = None
    start_month: Annotated[Optional[int], Field(description='Start month', default=None)] = None
    end_date: Annotated[Optional[date], Field(description='End date of role', default=None)] = None
    end_year: Annotated[Optional[int], Field(description='End year', default=None)] = None
    end_month: Annotated[Optional[int], Field(description='End month', default=None)] = None
    end_date_text: Annotated[Optional[str], Field(description='Textual end date like "Present"', default=None)] = None
    seniority_level: Annotated[Optional[str], Field(description='Estimated seniority level', default=None)] = None
    function_area: Annotated[Optional[str], Field(description='Function area or department', default=None)] = None
    location: Annotated[Optional[str], Field(description='Location of the role', default=None)] = None
    description: Annotated[Optional[str], Field(description='Description of the role/experience', default=None)] = None
    raw_experience: Annotated[Optional[str], Field(description='Raw JSON payload of experience data', default=None)] = None


class GetExperienceByIdRequestSchema(BaseRequestSchema):
    experience_id: Optional[str] = None


class DeleteExperienceByIdRequestSchema(BaseRequestSchema):
    experience_id: Optional[str] = None


class ListExperiencesResponseSchema(PaginateResponseSchema):
    experiences: List[ExperienceSchema]


class CreateExperienceResponseSchema(BaseResponseSchema):
    experience: ExperienceSchema


class CreateExperiencesResponseSchema(BaseResponseSchema):
    experiences: List[ExperienceSchema]


class UpdateExperienceResponseSchema(BaseResponseSchema):
    experience: ExperienceSchema


class GetExperienceByIdResponseSchema(BaseResponseSchema):
    experience: ExperienceSchema
