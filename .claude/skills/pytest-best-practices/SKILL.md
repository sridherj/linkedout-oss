---
name: pytest-best-practices
user_invocable: true
description: Apply pytest best practices when writing test files. Use when creating test_*.py files, writing test classes and methods, or ensuring test quality and coverage.
---

# PytestBestPractices Skill

Apply these pytest best practices when writing or reviewing tests.

## Reference Files
- `./reference_code/.cursor/rules/pytest.mdc`
- `./reference_code/conftest.py`
- `./reference_code/tests/projects/` (example tests)

## Naming Conventions

| Type | Prefix | Example |
|------|--------|---------|
| Mock objects | `mock_` | `mock_service`, `mock_repository` |
| Fake objects | `fake_` | `fake_client`, `fake_api` |
| Test data | `test_` | `test_project_id`, `test_tenant_id` |
| Expected values | `expected_` | `expected_count`, `expected_name` |
| Actual results | `actual_` | `actual_projects`, `actual_result` |

## Test Structure

### Arrange-Act-Assert Pattern
```python
def test_something(self, repository, test_tenant_id):
    # Arrange - set up test data and expectations
    expected_count = 5
    expected_status = ProjectStatus.ACTIVE

    # Act - call the method under test
    actual_results = repository.list_with_filters(
        tenant_id=test_tenant_id,
        status=[expected_status]
    )

    # Assert - verify results
    assert len(actual_results) == expected_count
    assert all(r.status == expected_status for r in actual_results)
```

## Key Rules

### Use Enums, Not Strings
```python
# WRONG
status='ACTIVE'

# CORRECT
status=ProjectStatus.ACTIVE
```

### Use DateTimeComparator for Timestamps
SQLite has timezone issues and JSON responses may serialize datetimes in local timezone - use the helper from conftest:
```python
# Repository tests (comparing entity attributes)
def test_created_at(self, datetime_comparator):
    expected_time = datetime.now(timezone.utc)
    # ... create entity ...
    assert datetime_comparator(expected_time) == actual_entity.created_at

# Integration tests (comparing JSON response datetimes)
def test_update_times(self, test_client, datetime_comparator):
    response = test_client.patch('/endpoint', json={'start_time': '2024-01-01T06:00:00Z'})
    data = response.json()
    # Parse ISO string and compare with DateTimeComparator
    actual_time = datetime.fromisoformat(data['entity']['start_time'])
    expected_time = datetime(2024, 1, 1, 6, 0, tzinfo=timezone.utc)
    assert datetime_comparator(expected_time) == actual_time
```

**Never** do string-based time assertions like `assert '06:00:00' in response['time']` - they break across timezones.

### Repository Tests: Two Patterns
1. **Read-only tests**: Use `shared_db_session` (faster, shared DB)
2. **Mutation tests**: Use `class_scoped_isolated_db_session` (isolated DB)

### Always Commit After Mutations
```python
def test_create(self, repository, db_session):
    entity = repository.create(new_entity)
    db_session.commit()  # Required for mutations
    assert entity.id is not None
```

### Mock with autospec for Type Safety
```python
@pytest.fixture
def mock_project_repository() -> Mock:
    # - autospec enforces method signatures
    # - spec_set prevents accessing/setting attributes that don't exist
    return create_autospec(ProjectRepository, instance=True, spec_set=True)
```

### Fixtures Must Have Return Type Annotations
```python
@pytest.fixture
def project_service(mock_session: Mock) -> ProjectService:
    return ProjectService(mock_session)
```

### Focus on Behavior, Not Implementation
Test what the function does, not how it does it.

## Test Coverage Goals

For each layer:
- **Repository**: list (with all filters), count, get_by_id (found/not found), create, update, delete
- **Service**: All methods + error cases (not found, assertion errors)
- **Controller**: All endpoints + status codes + error cases

## Common Mistakes to Avoid

1. Using strings instead of enums
2. Forgetting `db_session.commit()` after mutations
3. Mocking without `spec=` parameter
4. Making strict timestamp assertions (use DateTimeComparator, never string-match times in JSON)
5. Testing implementation instead of behavior
6. Missing error case tests
