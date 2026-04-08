# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for RoleAlias API."""
from enum import StrEnum
from typing import List, Optional

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.role_alias.schemas.role_alias_schema import RoleAliasSchema


class RoleAliasSortByFields(StrEnum):
    ALIAS_TITLE = 'alias_title'
    CANONICAL_TITLE = 'canonical_title'
    CREATED_AT = 'created_at'


class ListRoleAliasesRequestSchema(PaginateRequestSchema):
    sort_by: RoleAliasSortByFields = RoleAliasSortByFields.ALIAS_TITLE
    sort_order: SortOrder = SortOrder.ASC
    alias_title: Optional[str] = None
    canonical_title: Optional[str] = None
    seniority_level: Optional[str] = None
    function_area: Optional[str] = None


class CreateRoleAliasRequestSchema(BaseRequestSchema):
    alias_title: str
    canonical_title: str
    seniority_level: Optional[str] = None
    function_area: Optional[str] = None


class CreateRoleAliasesRequestSchema(BaseRequestSchema):
    role_aliases: List[CreateRoleAliasRequestSchema]


class UpdateRoleAliasRequestSchema(BaseRequestSchema):
    role_alias_id: Optional[str] = None
    alias_title: Optional[str] = None
    canonical_title: Optional[str] = None
    seniority_level: Optional[str] = None
    function_area: Optional[str] = None


class GetRoleAliasByIdRequestSchema(BaseRequestSchema):
    role_alias_id: Optional[str] = None


class DeleteRoleAliasByIdRequestSchema(BaseRequestSchema):
    role_alias_id: Optional[str] = None


class ListRoleAliasesResponseSchema(PaginateResponseSchema):
    role_aliases: List[RoleAliasSchema]


class CreateRoleAliasResponseSchema(BaseResponseSchema):
    role_alias: RoleAliasSchema


class CreateRoleAliasesResponseSchema(BaseResponseSchema):
    role_aliases: List[RoleAliasSchema]


class UpdateRoleAliasResponseSchema(BaseResponseSchema):
    role_alias: RoleAliasSchema


class GetRoleAliasByIdResponseSchema(BaseResponseSchema):
    role_alias: RoleAliasSchema
