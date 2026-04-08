# SPDX-License-Identifier: Apache-2.0
"""Repository for CompanyAlias entity (shared, no tenant/BU scoping)."""
from typing import List, Optional

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from common.schemas.base_enums_schemas import SortOrder
from linkedout.company_alias.entities.company_alias_entity import CompanyAliasEntity
from linkedout.company_alias.schemas.company_alias_api_schema import CompanyAliasSortByFields
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class CompanyAliasRepository:
    """
    Repository for CompanyAlias entity.

    CompanyAlias is a shared entity with no tenant/BU scoping.
    Follows the same pattern as CompanyRepository.
    """

    def __init__(self, session: Session):
        self._session = session
        logger.debug('Initialized CompanyAliasRepository with database session')

    def list_with_filters(
        self,
        limit: int = 20,
        offset: int = 0,
        sort_by: CompanyAliasSortByFields = CompanyAliasSortByFields.ALIAS_NAME,
        sort_order: SortOrder = SortOrder.ASC,
        alias_name: Optional[str] = None,
        company_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[CompanyAliasEntity]:
        """List company aliases with filters, sorting, and pagination."""
        logger.debug(f'Fetching company aliases - sort_by: {sort_by}, sort_order: {sort_order}')

        query = self._session.query(CompanyAliasEntity)

        # Apply filters
        if alias_name:
            query = query.filter(CompanyAliasEntity.alias_name.ilike(f'%{alias_name}%'))
        if company_id:
            query = query.filter(CompanyAliasEntity.company_id == company_id)
        if source:
            query = query.filter(CompanyAliasEntity.source == source)

        # Apply sorting
        sort_column = getattr(CompanyAliasEntity, sort_by, CompanyAliasEntity.alias_name)
        if sort_order == SortOrder.DESC:
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        results = query.limit(limit).offset(offset).all()
        logger.debug(f'Fetched {len(results)} company aliases (limit: {limit}, offset: {offset})')
        return results

    def count_with_filters(
        self,
        alias_name: Optional[str] = None,
        company_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> int:
        """Count company aliases matching filters."""
        logger.debug('Counting company aliases')

        query = self._session.query(CompanyAliasEntity)

        if alias_name:
            query = query.filter(CompanyAliasEntity.alias_name.ilike(f'%{alias_name}%'))
        if company_id:
            query = query.filter(CompanyAliasEntity.company_id == company_id)
        if source:
            query = query.filter(CompanyAliasEntity.source == source)

        count = query.count()
        logger.debug(f'Total company alias count with filters: {count}')
        return count

    def create(self, company_alias: CompanyAliasEntity) -> CompanyAliasEntity:
        """Create a new company alias."""
        assert company_alias.alias_name is not None, 'Alias name is required'

        logger.debug(f'Creating company alias: {company_alias.alias_name}')
        try:
            self._session.add(company_alias)
            self._session.flush()
            self._session.refresh(company_alias)
            logger.info(f'Successfully created company alias with ID: {company_alias.id}')
            return company_alias
        except Exception as e:
            logger.error(f'Failed to create company alias: {str(e)}')
            raise

    def get_by_id(self, company_alias_id: str) -> Optional[CompanyAliasEntity]:
        """Get a company alias by ID."""
        assert company_alias_id is not None, 'Company alias ID is required'

        logger.debug(f'Fetching company alias by ID: {company_alias_id}')
        try:
            company_alias = (
                self._session.query(CompanyAliasEntity)
                .filter(CompanyAliasEntity.id == company_alias_id)
                .one_or_none()
            )
            if company_alias is None:
                logger.debug(f'Company alias not found: {company_alias_id}')
            else:
                logger.info(f'Successfully fetched company alias: {company_alias_id}')
            return company_alias
        except Exception as e:
            logger.error(f'Failed to fetch company alias {company_alias_id}: {str(e)}')
            raise

    def update(self, company_alias: CompanyAliasEntity) -> CompanyAliasEntity:
        """Update a company alias."""
        assert company_alias.id is not None, 'Company alias ID is required'

        logger.debug(f'Updating company alias: {company_alias.id}')
        try:
            self._session.merge(company_alias)
            self._session.flush()
            self._session.refresh(company_alias)
            logger.info(f'Successfully updated company alias: {company_alias.id}')
            return company_alias
        except Exception as e:
            logger.error(f'Failed to update company alias: {str(e)}')
            raise

    def delete(self, company_alias: CompanyAliasEntity) -> None:
        """Delete a company alias."""
        assert company_alias.id is not None, 'Company alias ID is required'

        logger.debug(f'Deleting company alias: {company_alias.id}')
        try:
            self._session.delete(company_alias)
            logger.info(f'Successfully deleted company alias: {company_alias.id}')
        except Exception as e:
            logger.error(f'Failed to delete company alias: {str(e)}')
            raise
