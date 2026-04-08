# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for EnrichmentConfig API."""
from enum import StrEnum
from typing import List, Optional

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from organization.enrichment_config.schemas.enrichment_config_schema import EnrichmentConfigSchema


class EnrichmentConfigSortByFields(StrEnum):
    CREATED_AT = 'created_at'
    ENRICHMENT_MODE = 'enrichment_mode'


class ListEnrichmentConfigsRequestSchema(PaginateRequestSchema):
    sort_by: EnrichmentConfigSortByFields = EnrichmentConfigSortByFields.CREATED_AT
    sort_order: SortOrder = SortOrder.DESC
    app_user_id: Optional[str] = None
    enrichment_mode: Optional[str] = None
    enrichment_config_ids: Optional[list[str]] = None


class CreateEnrichmentConfigRequestSchema(BaseRequestSchema):
    app_user_id: str
    enrichment_mode: str = 'platform'
    apify_key_encrypted: Optional[str] = None
    apify_key_hint: Optional[str] = None


class CreateEnrichmentConfigsRequestSchema(BaseRequestSchema):
    enrichment_configs: List[CreateEnrichmentConfigRequestSchema]


class UpdateEnrichmentConfigRequestSchema(BaseRequestSchema):
    enrichment_config_id: Optional[str] = None
    enrichment_mode: Optional[str] = None
    apify_key_encrypted: Optional[str] = None
    apify_key_hint: Optional[str] = None


class GetEnrichmentConfigByIdRequestSchema(BaseRequestSchema):
    enrichment_config_id: Optional[str] = None


class DeleteEnrichmentConfigByIdRequestSchema(BaseRequestSchema):
    enrichment_config_id: Optional[str] = None


class ListEnrichmentConfigsResponseSchema(PaginateResponseSchema):
    enrichment_configs: List[EnrichmentConfigSchema]


class CreateEnrichmentConfigResponseSchema(BaseResponseSchema):
    enrichment_config: EnrichmentConfigSchema


class CreateEnrichmentConfigsResponseSchema(BaseResponseSchema):
    enrichment_configs: List[EnrichmentConfigSchema]


class UpdateEnrichmentConfigResponseSchema(BaseResponseSchema):
    enrichment_config: EnrichmentConfigSchema


class GetEnrichmentConfigByIdResponseSchema(BaseResponseSchema):
    enrichment_config: EnrichmentConfigSchema
