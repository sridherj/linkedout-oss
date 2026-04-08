# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for Education API."""
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.education.schemas.education_schema import EducationSchema


class EducationSortByFields(StrEnum):
    CREATED_AT = 'created_at'
    SCHOOL_NAME = 'school_name'
    END_YEAR = 'end_year'


class ListEducationsRequestSchema(PaginateRequestSchema):
    sort_by: Annotated[EducationSortByFields, Field(default=EducationSortByFields.CREATED_AT, description='Sort field')]
    sort_order: Annotated[SortOrder, Field(default=SortOrder.ASC, description='Sort order')]
    crawled_profile_id: Annotated[Optional[str], Field(default=None, description='Filter by profile ID')]
    school_name: Annotated[Optional[str], Field(default=None, description='Filter by school name')]
    degree: Annotated[Optional[str], Field(default=None, description='Filter by degree')]


class CreateEducationRequestSchema(BaseRequestSchema):
    crawled_profile_id: Annotated[str, Field(description='Profile this education belongs to')]
    school_name: Annotated[Optional[str], Field(default=None, description='Name of the school/university')]
    school_linkedin_url: Annotated[Optional[str], Field(default=None, description='LinkedIn URL of the school')]
    degree: Annotated[Optional[str], Field(default=None, description='Degree obtained')]
    field_of_study: Annotated[Optional[str], Field(default=None, description='Field of study / major')]
    start_year: Annotated[Optional[int], Field(default=None, description='Year started')]
    end_year: Annotated[Optional[int], Field(default=None, description='Year ended or expected to end')]
    description: Annotated[Optional[str], Field(default=None, description='Additional description about the education')]
    raw_education: Annotated[Optional[str], Field(default=None, description='Raw JSON payload of education data')]


class CreateEducationsRequestSchema(BaseRequestSchema):
    educations: Annotated[List[CreateEducationRequestSchema], Field(description='List of items to create')]


class UpdateEducationRequestSchema(BaseRequestSchema):
    education_id: Annotated[Optional[str], Field(default=None, description='ID of the education to update')]
    school_name: Annotated[Optional[str], Field(default=None, description='Name of the school/university')]
    school_linkedin_url: Annotated[Optional[str], Field(default=None, description='LinkedIn URL of the school')]
    degree: Annotated[Optional[str], Field(default=None, description='Degree obtained')]
    field_of_study: Annotated[Optional[str], Field(default=None, description='Field of study / major')]
    start_year: Annotated[Optional[int], Field(default=None, description='Year started')]
    end_year: Annotated[Optional[int], Field(default=None, description='Year ended or expected to end')]
    description: Annotated[Optional[str], Field(default=None, description='Additional description about the education')]
    raw_education: Annotated[Optional[str], Field(default=None, description='Raw JSON payload of education data')]


class GetEducationByIdRequestSchema(BaseRequestSchema):
    education_id: Annotated[Optional[str], Field(default=None, description='ID of the education to retrieve')]


class DeleteEducationByIdRequestSchema(BaseRequestSchema):
    education_id: Annotated[Optional[str], Field(default=None, description='ID of the education to delete')]


class ListEducationsResponseSchema(PaginateResponseSchema):
    educations: Annotated[List[EducationSchema], Field(description='List of educations')]


class CreateEducationResponseSchema(BaseResponseSchema):
    education: Annotated[EducationSchema, Field(description='Created education')]


class CreateEducationsResponseSchema(BaseResponseSchema):
    educations: Annotated[List[EducationSchema], Field(description='Created educations')]


class UpdateEducationResponseSchema(BaseResponseSchema):
    education: Annotated[EducationSchema, Field(description='Updated education')]


class GetEducationByIdResponseSchema(BaseResponseSchema):
    education: Annotated[EducationSchema, Field(description='Retrieved education')]
