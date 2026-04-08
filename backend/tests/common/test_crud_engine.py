# SPDX-License-Identifier: Apache-2.0
"""Engine tests for generic CRUD base classes.

Tests all BaseRepository and BaseService methods ONCE using a dummy CRUDTestEntity.
Uses SQLite in-memory for fast, isolated testing without external dependencies.

These tests validate the "engine" - the generic CRUD logic that all entities inherit.
Entity-specific tests only need to verify "wiring" (correct configuration).
"""

import pytest
from datetime import datetime, timezone
from enum import StrEnum
from typing import List, Optional
from unittest.mock import Mock

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, String, create_engine
from sqlalchemy.orm import Session, sessionmaker

from common.entities.base_entity import Base, BaseEntity
from common.repositories.base_repository import BaseRepository, FilterSpec
from common.schemas.base_enums_schemas import SortOrder
from common.services.base_service import BaseService


# =============================================================================
# TEST ENTITY DEFINITION (Dummy entity for testing only)
# =============================================================================


class CRUDTestEntity(BaseEntity):
    """Minimal entity for testing BaseRepository and BaseService."""

    __tablename__ = 'dummy_test_entity'
    id_prefix = 'test_'

    tenant_id = Column(String, nullable=False)
    bu_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    status = Column(String, default='active')


class CRUDSortByFields(StrEnum):
    """Sort fields for CRUDTestEntity."""

    NAME = 'name'
    CATEGORY = 'category'
    CREATED_AT = 'created_at'


class CRUDTestSchema(BaseModel):
    """Pydantic schema for CRUDTestEntity."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    bu_id: str
    name: str
    category: Optional[str] = None
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# TEST REPOSITORY AND SERVICE IMPLEMENTATIONS
# =============================================================================


class CRUDTestRepository(BaseRepository[CRUDTestEntity, CRUDSortByFields]):
    """Minimal repository implementation for testing."""

    _entity_class = CRUDTestEntity
    _default_sort_field = 'name'
    _entity_name = 'test'

    def _get_filter_specs(self) -> List[FilterSpec]:
        return [
            FilterSpec('category', 'eq'),
            FilterSpec('statuses', 'in', entity_field='status'),
            FilterSpec('search', 'ilike', entity_field='name'),
        ]


class CRUDTestService(BaseService[CRUDTestEntity, CRUDTestSchema, CRUDTestRepository]):
    """Minimal service implementation for testing."""

    _repository_class = CRUDTestRepository
    _schema_class = CRUDTestSchema
    _entity_class = CRUDTestEntity
    _entity_name = 'test'
    _entity_id_field = 'test_id'

    def _extract_filter_kwargs(self, list_request) -> dict:
        return {
            'category': getattr(list_request, 'category', None),
            'statuses': getattr(list_request, 'statuses', None),
            'search': getattr(list_request, 'search', None),
        }

    def _create_entity_from_request(self, create_request) -> CRUDTestEntity:
        return CRUDTestEntity(
            tenant_id=create_request.tenant_id,
            bu_id=create_request.bu_id,
            name=create_request.name,
            category=getattr(create_request, 'category', None),
            status=getattr(create_request, 'status', 'active'),
        )

    def _update_entity_from_request(self, entity: CRUDTestEntity, update_request) -> None:
        if getattr(update_request, 'name', None) is not None:
            entity.name = update_request.name
        if getattr(update_request, 'category', None) is not None:
            entity.category = update_request.category
        if getattr(update_request, 'status', None) is not None:
            entity.status = update_request.status


# =============================================================================
# REQUEST SCHEMAS FOR SERVICE TESTS
# =============================================================================


class ListTestRequest:
    """Mock list request for testing."""

    def __init__(
        self,
        tenant_id: str = 'tenant_1',
        bu_id: str = 'bu_1',
        limit: int = 20,
        offset: int = 0,
        sort_by: Optional[CRUDSortByFields] = None,
        sort_order: SortOrder = SortOrder.ASC,
        is_active: Optional[bool] = None,
        category: Optional[str] = None,
        statuses: Optional[List[str]] = None,
        search: Optional[str] = None,
    ):
        self.tenant_id = tenant_id
        self.bu_id = bu_id
        self.limit = limit
        self.offset = offset
        self.sort_by = sort_by
        self.sort_order = sort_order
        self.is_active = is_active
        self.category = category
        self.statuses = statuses
        self.search = search


class CreateTestRequest:
    """Mock create request for testing."""

    def __init__(
        self,
        tenant_id: str = 'tenant_1',
        bu_id: str = 'bu_1',
        name: str = 'Test Item',
        category: Optional[str] = None,
        status: str = 'active',
    ):
        self.tenant_id = tenant_id
        self.bu_id = bu_id
        self.name = name
        self.category = category
        self.status = status


class UpdateTestRequest:
    """Mock update request for testing."""

    def __init__(
        self,
        tenant_id: str = 'tenant_1',
        bu_id: str = 'bu_1',
        test_id: str = 'test_123',
        name: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ):
        self.tenant_id = tenant_id
        self.bu_id = bu_id
        self.test_id = test_id
        self.name = name
        self.category = category
        self.status = status


class GetTestRequest:
    """Mock get-by-ID request for testing."""

    def __init__(
        self,
        tenant_id: str = 'tenant_1',
        bu_id: str = 'bu_1',
        test_id: str = 'test_123',
    ):
        self.tenant_id = tenant_id
        self.bu_id = bu_id
        self.test_id = test_id


class DeleteTestRequest:
    """Mock delete request for testing."""

    def __init__(
        self,
        tenant_id: str = 'tenant_1',
        bu_id: str = 'bu_1',
        test_id: str = 'test_123',
    ):
        self.tenant_id = tenant_id
        self.bu_id = bu_id
        self.test_id = test_id


# =============================================================================
# SQLITE IN-MEMORY FIXTURES
# =============================================================================


@pytest.fixture
def sqlite_engine():
    """Create SQLite in-memory engine for testing (per test for isolation)."""
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(sqlite_engine):
    """Create a new database session for each test."""
    SessionLocal = sessionmaker(bind=sqlite_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def repository(db_session: Session) -> CRUDTestRepository:
    """Create a CRUDTestRepository instance."""
    return CRUDTestRepository(db_session)


@pytest.fixture
def service(db_session: Session) -> CRUDTestService:
    """Create a CRUDTestService instance."""
    return CRUDTestService(db_session)


@pytest.fixture
def seeded_entities(db_session: Session) -> List[CRUDTestEntity]:
    """Seed test data and return created entities."""
    entities = []
    categories = ['A', 'B', 'A', 'C', 'B']
    statuses = ['active', 'active', 'inactive', 'active', 'pending']

    for i in range(5):
        entity = CRUDTestEntity(
            tenant_id='tenant_1',
            bu_id='bu_1',
            name=f'Item {i + 1}',
            category=categories[i],
            status=statuses[i],
        )
        db_session.add(entity)
        entities.append(entity)

    db_session.flush()
    return entities


# =============================================================================
# REPOSITORY ENGINE TESTS
# =============================================================================


class TestBaseRepositoryListWithFilters:
    """Tests for BaseRepository.list_with_filters method."""

    def test_returns_all_entities(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that list_with_filters returns all entities."""
        results = repository.list_with_filters(
            tenant_id='tenant_1',
            bu_id='bu_1',
        )
        assert len(results) == 5

    def test_respects_limit(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that limit parameter is respected."""
        results = repository.list_with_filters(
            tenant_id='tenant_1',
            bu_id='bu_1',
            limit=2,
        )
        assert len(results) == 2

    def test_respects_offset(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that offset parameter is respected."""
        all_results = repository.list_with_filters(
            tenant_id='tenant_1',
            bu_id='bu_1',
        )
        offset_results = repository.list_with_filters(
            tenant_id='tenant_1',
            bu_id='bu_1',
            offset=2,
        )
        assert len(offset_results) == len(all_results) - 2

    def test_sorts_ascending(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test ascending sort order."""
        results = repository.list_with_filters(
            tenant_id='tenant_1',
            bu_id='bu_1',
            sort_by=CRUDSortByFields.NAME,
            sort_order=SortOrder.ASC,
        )
        names = [r.name for r in results]
        assert names == sorted(names)

    def test_sorts_descending(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test descending sort order."""
        results = repository.list_with_filters(
            tenant_id='tenant_1',
            bu_id='bu_1',
            sort_by=CRUDSortByFields.NAME,
            sort_order=SortOrder.DESC,
        )
        names = [r.name for r in results]
        assert names == sorted(names, reverse=True)

    def test_filter_eq(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test equality filter (eq)."""
        results = repository.list_with_filters(
            tenant_id='tenant_1',
            bu_id='bu_1',
            category='A',
        )
        assert len(results) == 2
        for r in results:
            assert r.category == 'A'

    def test_filter_in(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test in-list filter (in)."""
        results = repository.list_with_filters(
            tenant_id='tenant_1',
            bu_id='bu_1',
            statuses=['active', 'pending'],
        )
        assert len(results) == 4
        for r in results:
            assert r.status in ['active', 'pending']

    def test_filter_ilike(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test case-insensitive like filter (ilike)."""
        results = repository.list_with_filters(
            tenant_id='tenant_1',
            bu_id='bu_1',
            search='item',
        )
        assert len(results) == 5  # All items contain 'item'

    def test_filter_is_active(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test is_active filter."""
        results = repository.list_with_filters(
            tenant_id='tenant_1',
            bu_id='bu_1',
            is_active=True,
        )
        for r in results:
            assert r.is_active is True

    def test_tenant_scoping(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that results are scoped to tenant."""
        results = repository.list_with_filters(
            tenant_id='other_tenant',
            bu_id='bu_1',
        )
        assert len(results) == 0


class TestBaseRepositoryCountWithFilters:
    """Tests for BaseRepository.count_with_filters method."""

    def test_returns_total_count(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that count returns total count."""
        count = repository.count_with_filters(
            tenant_id='tenant_1',
            bu_id='bu_1',
        )
        assert count == 5

    def test_count_with_filter(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test count with filter applied."""
        count = repository.count_with_filters(
            tenant_id='tenant_1',
            bu_id='bu_1',
            category='A',
        )
        assert count == 2


class TestBaseRepositoryGetById:
    """Tests for BaseRepository.get_by_id method."""

    def test_returns_entity_when_found(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that get_by_id returns entity when found."""
        expected_id = seeded_entities[0].id
        result = repository.get_by_id(
            tenant_id='tenant_1',
            bu_id='bu_1',
            entity_id=expected_id,
        )
        assert result is not None
        assert result.id == expected_id

    def test_returns_none_when_not_found(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that get_by_id returns None when not found."""
        result = repository.get_by_id(
            tenant_id='tenant_1',
            bu_id='bu_1',
            entity_id='nonexistent_id',
        )
        assert result is None


class TestBaseRepositoryGetByIds:
    """Tests for BaseRepository.get_by_ids method."""

    def test_returns_matching_entities(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that get_by_ids returns all matching entities."""
        expected_ids = [seeded_entities[0].id, seeded_entities[1].id]
        results = repository.get_by_ids(
            tenant_id='tenant_1',
            bu_id='bu_1',
            entity_ids=expected_ids,
        )
        assert len(results) == 2
        actual_ids = {r.id for r in results}
        assert actual_ids == set(expected_ids)

    def test_returns_empty_for_no_matches(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that get_by_ids returns empty list when no matches."""
        results = repository.get_by_ids(
            tenant_id='tenant_1',
            bu_id='bu_1',
            entity_ids=['nonexistent_1', 'nonexistent_2'],
        )
        assert len(results) == 0

    def test_returns_empty_for_empty_list(
        self,
        repository: CRUDTestRepository,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that get_by_ids returns empty list when given empty list."""
        results = repository.get_by_ids(
            tenant_id='tenant_1',
            bu_id='bu_1',
            entity_ids=[],
        )
        assert len(results) == 0


class TestBaseRepositoryCreate:
    """Tests for BaseRepository.create method."""

    def test_creates_entity_with_id(
        self,
        repository: CRUDTestRepository,
        db_session: Session,
    ):
        """Test that create generates ID and persists entity."""
        entity = CRUDTestEntity(
            tenant_id='tenant_1',
            bu_id='bu_1',
            name='New Item',
            category='X',
        )
        result = repository.create(entity)
        db_session.commit()

        assert result.id is not None
        assert result.id.startswith('test_')
        assert result.name == 'New Item'
        assert result.created_at is not None

    def test_creates_entity_with_timestamps(
        self,
        repository: CRUDTestRepository,
        db_session: Session,
    ):
        """Test that create sets timestamps."""
        entity = CRUDTestEntity(
            tenant_id='tenant_1',
            bu_id='bu_1',
            name='Timestamped Item',
        )
        result = repository.create(entity)
        db_session.commit()

        assert result.created_at is not None
        assert result.updated_at is not None


class TestBaseRepositoryUpdate:
    """Tests for BaseRepository.update method."""

    def test_updates_entity(
        self,
        repository: CRUDTestRepository,
        db_session: Session,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that update persists changes."""
        entity = seeded_entities[0]
        entity.name = 'Updated Name'

        result = repository.update(entity)
        db_session.commit()

        # Verify by fetching again
        fetched = repository.get_by_id(
            tenant_id='tenant_1',
            bu_id='bu_1',
            entity_id=entity.id,
        )
        assert fetched.name == 'Updated Name'


class TestBaseRepositoryDelete:
    """Tests for BaseRepository.delete method."""

    def test_deletes_entity(
        self,
        repository: CRUDTestRepository,
        db_session: Session,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that delete removes entity."""
        entity = seeded_entities[0]
        entity_id = entity.id

        # Verify exists
        assert (
            repository.get_by_id(
                tenant_id='tenant_1',
                bu_id='bu_1',
                entity_id=entity_id,
            )
            is not None
        )

        repository.delete(entity)
        db_session.commit()

        # Verify deleted
        result = repository.get_by_id(
            tenant_id='tenant_1',
            bu_id='bu_1',
            entity_id=entity_id,
        )
        assert result is None


# =============================================================================
# SERVICE ENGINE TESTS
# =============================================================================


class TestBaseServiceListEntities:
    """Tests for BaseService.list_entities method."""

    def test_returns_schemas_and_count(
        self,
        service: CRUDTestService,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that list_entities returns schemas and total count."""
        request = ListTestRequest()
        schemas, count = service.list_entities(request)

        assert count == 5
        assert len(schemas) == 5
        assert all(isinstance(s, CRUDTestSchema) for s in schemas)

    def test_returns_empty_for_no_matches(
        self,
        service: CRUDTestService,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that list_entities returns empty for no matches."""
        request = ListTestRequest(tenant_id='other_tenant')
        schemas, count = service.list_entities(request)

        assert count == 0
        assert len(schemas) == 0


class TestBaseServiceCreateEntity:
    """Tests for BaseService.create_entity method."""

    def test_creates_and_returns_schema(
        self,
        service: CRUDTestService,
        db_session: Session,
    ):
        """Test that create_entity returns schema."""
        request = CreateTestRequest(name='Service Created')
        result = service.create_entity(request)
        db_session.commit()

        assert isinstance(result, CRUDTestSchema)
        assert result.name == 'Service Created'
        assert result.id.startswith('test_')


class TestBaseServiceUpdateEntity:
    """Tests for BaseService.update_entity method."""

    def test_updates_and_returns_schema(
        self,
        service: CRUDTestService,
        db_session: Session,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that update_entity updates and returns schema."""
        request = UpdateTestRequest(
            test_id=seeded_entities[0].id,
            name='Updated via Service',
        )
        result = service.update_entity(request)
        db_session.commit()

        assert isinstance(result, CRUDTestSchema)
        assert result.name == 'Updated via Service'

    def test_raises_when_not_found(
        self,
        service: CRUDTestService,
    ):
        """Test that update_entity raises ValueError when not found."""
        request = UpdateTestRequest(test_id='nonexistent_id', name='Update')

        with pytest.raises(ValueError) as exc_info:
            service.update_entity(request)

        assert 'not found' in str(exc_info.value).lower()


class TestBaseServiceGetEntityById:
    """Tests for BaseService.get_entity_by_id method."""

    def test_returns_schema_when_found(
        self,
        service: CRUDTestService,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that get_entity_by_id returns schema when found."""
        request = GetTestRequest(test_id=seeded_entities[0].id)
        result = service.get_entity_by_id(request)

        assert result is not None
        assert isinstance(result, CRUDTestSchema)
        assert result.id == seeded_entities[0].id

    def test_returns_none_when_not_found(
        self,
        service: CRUDTestService,
    ):
        """Test that get_entity_by_id returns None when not found."""
        request = GetTestRequest(test_id='nonexistent_id')
        result = service.get_entity_by_id(request)

        assert result is None


class TestBaseServiceDeleteEntityById:
    """Tests for BaseService.delete_entity_by_id method."""

    def test_deletes_entity(
        self,
        service: CRUDTestService,
        db_session: Session,
        seeded_entities: List[CRUDTestEntity],
    ):
        """Test that delete_entity_by_id deletes entity."""
        entity_id = seeded_entities[0].id
        delete_request = DeleteTestRequest(test_id=entity_id)
        service.delete_entity_by_id(delete_request)
        db_session.commit()

        # Verify deleted
        get_request = GetTestRequest(test_id=entity_id)
        result = service.get_entity_by_id(get_request)
        assert result is None

    def test_raises_when_not_found(
        self,
        service: CRUDTestService,
    ):
        """Test that delete_entity_by_id raises ValueError when not found."""
        request = DeleteTestRequest(test_id='nonexistent_id')

        with pytest.raises(ValueError) as exc_info:
            service.delete_entity_by_id(request)

        assert 'not found' in str(exc_info.value).lower()
