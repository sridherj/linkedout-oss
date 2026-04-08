# SPDX-License-Identifier: Apache-2.0
"""Repository for Company entity (shared, no tenant/BU scoping)."""
from typing import List, Optional

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from common.schemas.base_enums_schemas import SortOrder
from linkedout.company.entities.company_entity import CompanyEntity
from linkedout.company.schemas.company_api_schema import CompanySortByFields
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class CompanyRepository:
    """
    Repository for Company entity.

    Company is a shared entity with no tenant/BU scoping.
    Follows the same pattern as TenantRepository.
    """

    def __init__(self, session: Session):
        self._session = session
        logger.debug('Initialized CompanyRepository with database session')

    def list_with_filters(
        self,
        limit: int = 20,
        offset: int = 0,
        sort_by: CompanySortByFields = CompanySortByFields.CANONICAL_NAME,
        sort_order: SortOrder = SortOrder.ASC,
        canonical_name: Optional[str] = None,
        domain: Optional[str] = None,
        industry: Optional[str] = None,
        size_tier: Optional[str] = None,
        hq_country: Optional[str] = None,
        company_ids: Optional[List[str]] = None,
    ) -> List[CompanyEntity]:
        """List companies with filters, sorting, and pagination."""
        logger.debug(f'Fetching companies - sort_by: {sort_by}, sort_order: {sort_order}')

        query = self._session.query(CompanyEntity)

        # Apply filters
        if canonical_name:
            query = query.filter(CompanyEntity.canonical_name.ilike(f'%{canonical_name}%'))
        if domain:
            query = query.filter(CompanyEntity.domain.ilike(f'%{domain}%'))
        if industry:
            query = query.filter(CompanyEntity.industry == industry)
        if size_tier:
            query = query.filter(CompanyEntity.size_tier == size_tier)
        if hq_country:
            query = query.filter(CompanyEntity.hq_country == hq_country)
        if company_ids:
            query = query.filter(CompanyEntity.id.in_(company_ids))

        # Apply sorting
        sort_column = getattr(CompanyEntity, sort_by, CompanyEntity.canonical_name)
        if sort_order == SortOrder.DESC:
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        results = query.limit(limit).offset(offset).all()
        logger.debug(f'Fetched {len(results)} companies (limit: {limit}, offset: {offset})')
        return results

    def count_with_filters(
        self,
        canonical_name: Optional[str] = None,
        domain: Optional[str] = None,
        industry: Optional[str] = None,
        size_tier: Optional[str] = None,
        hq_country: Optional[str] = None,
        company_ids: Optional[List[str]] = None,
    ) -> int:
        """Count companies matching filters."""
        logger.debug('Counting companies')

        query = self._session.query(CompanyEntity)

        if canonical_name:
            query = query.filter(CompanyEntity.canonical_name.ilike(f'%{canonical_name}%'))
        if domain:
            query = query.filter(CompanyEntity.domain.ilike(f'%{domain}%'))
        if industry:
            query = query.filter(CompanyEntity.industry == industry)
        if size_tier:
            query = query.filter(CompanyEntity.size_tier == size_tier)
        if hq_country:
            query = query.filter(CompanyEntity.hq_country == hq_country)
        if company_ids:
            query = query.filter(CompanyEntity.id.in_(company_ids))

        count = query.count()
        logger.debug(f'Total company count with filters: {count}')
        return count

    def create(self, company: CompanyEntity) -> CompanyEntity:
        """Create a new company."""
        assert company.canonical_name is not None, 'Canonical name is required'

        logger.debug(f'Creating company: {company.canonical_name}')
        try:
            self._session.add(company)
            self._session.flush()
            self._session.refresh(company)
            logger.info(f'Successfully created company with ID: {company.id}')
            return company
        except Exception as e:
            logger.error(f'Failed to create company: {str(e)}')
            raise

    def get_by_id(self, company_id: str) -> Optional[CompanyEntity]:
        """Get a company by ID."""
        assert company_id is not None, 'Company ID is required'

        logger.debug(f'Fetching company by ID: {company_id}')
        try:
            company = (
                self._session.query(CompanyEntity)
                .filter(CompanyEntity.id == company_id)
                .one_or_none()
            )
            if company is None:
                logger.debug(f'Company not found: {company_id}')
            else:
                logger.info(f'Successfully fetched company: {company_id}')
            return company
        except Exception as e:
            logger.error(f'Failed to fetch company {company_id}: {str(e)}')
            raise

    def update(self, company: CompanyEntity) -> CompanyEntity:
        """Update a company."""
        assert company.id is not None, 'Company ID is required'

        logger.debug(f'Updating company: {company.id}')
        try:
            self._session.merge(company)
            self._session.flush()
            self._session.refresh(company)
            logger.info(f'Successfully updated company: {company.id}')
            return company
        except Exception as e:
            logger.error(f'Failed to update company: {str(e)}')
            raise

    def delete(self, company: CompanyEntity) -> None:
        """Delete a company."""
        assert company.id is not None, 'Company ID is required'

        logger.debug(f'Deleting company: {company.id}')
        try:
            self._session.delete(company)
            logger.info(f'Successfully deleted company: {company.id}')
        except Exception as e:
            logger.error(f'Failed to delete company: {str(e)}')
            raise
