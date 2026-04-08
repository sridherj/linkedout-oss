# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for CompanyAlias API."""
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.company_alias.schemas.company_alias_schema import CompanyAliasSchema


class CompanyAliasSortByFields(StrEnum):
    ALIAS_NAME = 'alias_name'
    CREATED_AT = 'created_at'
    SOURCE = 'source'


class ListCompanyAliasesRequestSchema(PaginateRequestSchema):
    sort_by: Annotated[CompanyAliasSortByFields, Field(default=CompanyAliasSortByFields.ALIAS_NAME, description='Field to sort by')]
    sort_order: Annotated[SortOrder, Field(default=SortOrder.ASC, description='Sort direction')]
    alias_name: Annotated[Optional[str], Field(default=None, description='Filter by alias name')]
    company_id: Annotated[Optional[str], Field(default=None, description='Filter by company ID')]
    source: Annotated[Optional[str], Field(default=None, description='Filter by discovery source')]


class CreateCompanyAliasRequestSchema(BaseRequestSchema):
    alias_name: Annotated[str, Field(description='Alternative company name')]
    company_id: Annotated[str, Field(description='Parent company ID')]
    source: Annotated[Optional[str], Field(default=None, description='Source system or provider')]


class CreateCompanyAliasesRequestSchema(BaseRequestSchema):
    company_aliases: Annotated[List[CreateCompanyAliasRequestSchema], Field(description='List of aliases to create')]


class UpdateCompanyAliasRequestSchema(BaseRequestSchema):
    company_alias_id: Annotated[Optional[str], Field(default=None, description='Company Alias ID')]
    alias_name: Annotated[Optional[str], Field(default=None, description='Updated alternative name')]
    company_id: Annotated[Optional[str], Field(default=None, description='Updated company ID')]
    source: Annotated[Optional[str], Field(default=None, description='Updated data source')]


class GetCompanyAliasByIdRequestSchema(BaseRequestSchema):
    company_alias_id: Annotated[Optional[str], Field(default=None, description='Company Alias ID')]


class DeleteCompanyAliasByIdRequestSchema(BaseRequestSchema):
    company_alias_id: Annotated[Optional[str], Field(default=None, description='Company Alias ID')]


class ListCompanyAliasesResponseSchema(PaginateResponseSchema):
    company_aliases: Annotated[List[CompanyAliasSchema], Field(description='List of matching company aliases')]


class CreateCompanyAliasResponseSchema(BaseResponseSchema):
    company_alias: Annotated[CompanyAliasSchema, Field(description='Created company alias')]


class CreateCompanyAliasesResponseSchema(BaseResponseSchema):
    company_aliases: Annotated[List[CompanyAliasSchema], Field(description='Created company aliases')]


class UpdateCompanyAliasResponseSchema(BaseResponseSchema):
    company_alias: Annotated[CompanyAliasSchema, Field(description='Updated company alias')]


class GetCompanyAliasByIdResponseSchema(BaseResponseSchema):
    company_alias: Annotated[CompanyAliasSchema, Field(description='Fetched company alias')]
