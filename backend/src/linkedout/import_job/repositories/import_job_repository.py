# SPDX-License-Identifier: Apache-2.0
"""Repository for ImportJob entity."""
from typing import List

from common.repositories.base_repository import BaseRepository, FilterSpec
from linkedout.import_job.entities.import_job_entity import ImportJobEntity
from linkedout.import_job.schemas.import_job_api_schema import ImportJobSortByFields


class ImportJobRepository(BaseRepository[ImportJobEntity, ImportJobSortByFields]):
    _entity_class = ImportJobEntity
    _default_sort_field = 'created_at'
    _entity_name = 'import_job'

    def _get_filter_specs(self) -> List[FilterSpec]:
        return [
            FilterSpec('app_user_id', 'eq'),
            FilterSpec('source_type', 'eq'),
            FilterSpec('status', 'eq'),
        ]
