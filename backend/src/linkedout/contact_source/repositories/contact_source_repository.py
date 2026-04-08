# SPDX-License-Identifier: Apache-2.0
"""Repository for ContactSource entity."""
from typing import List

from common.repositories.base_repository import BaseRepository, FilterSpec
from linkedout.contact_source.entities.contact_source_entity import ContactSourceEntity
from linkedout.contact_source.schemas.contact_source_api_schema import ContactSourceSortByFields


class ContactSourceRepository(BaseRepository[ContactSourceEntity, ContactSourceSortByFields]):
    _entity_class = ContactSourceEntity
    _default_sort_field = 'created_at'
    _entity_name = 'contact_source'

    def _get_filter_specs(self) -> List[FilterSpec]:
        return [
            FilterSpec('app_user_id', 'eq'),
            FilterSpec('import_job_id', 'eq'),
            FilterSpec('source_type', 'eq'),
            FilterSpec('dedup_status', 'eq'),
            FilterSpec('connection_id', 'eq'),
        ]
