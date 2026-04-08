---
name: python-best-practices
user_invocable: true
description: Apply these Python coding standards when writing or reviewing Python code. Use when creating new Python files, refactoring code, or ensuring code quality and style compliance.
---

# PythonBestPractices Skill

Apply these Python coding standards when writing or reviewing code.

## Reference
- `./reference_code/.cursor/rules/bestpractices.mdc`
- Google Python Style Guide: https://google.github.io/styleguide/pyguide.html

## Style Guidelines

### Naming Conventions
| Type | Convention | Example |
|------|------------|---------|
| Variables/functions | snake_case | `project_id`, `get_by_id()` |
| Classes | PascalCase | `ProjectService`, `ProjectEntity` |
| Constants | UPPER_SNAKE_CASE | `MAX_LIMIT`, `DEFAULT_STATUS` |
| Private members | Leading underscore | `_session`, `_repository` |

### Formatting
- 4 spaces per indentation level
- Max line length: 80 characters
- Private members start with `_` and must be typed

### Type Hints
```python
# Always include type hints
def get_project(self, project_id: str) -> Optional[ProjectSchema]:
    pass

# For class members
class Service:
    _session: Session
    _repository: ProjectRepository
```

## Code Design

### Small, Single-Responsibility Functions
```python
# GOOD - Single responsibility
def validate_tenant_id(tenant_id: str) -> None:
    assert tenant_id is not None, 'Tenant ID is required'

def fetch_project(self, tenant_id: str, project_id: str) -> ProjectEntity:
    return self._repository.get_by_id(tenant_id, project_id)

# BAD - Multiple responsibilities
def validate_and_fetch_project(self, tenant_id, project_id):
    if not tenant_id:
        raise ValueError("No tenant")
    # ... validation + fetching mixed
```

### Avoid Deep Nesting (Use Early Returns)
```python
# GOOD - Early returns
def process_project(self, project: Optional[ProjectEntity]) -> ProjectSchema:
    if project is None:
        raise ValueError('Project not found')
    if project.status == Status.DELETED:
        raise ValueError('Project is deleted')
    return ProjectSchema.model_validate(project)

# BAD - Deep nesting
def process_project(self, project):
    if project:
        if project.status != Status.DELETED:
            return ProjectSchema.model_validate(project)
        else:
            raise ValueError('Deleted')
    else:
        raise ValueError('Not found')
```

### Parameter Ordering: Stable Before Variable
Order parameters from least-changing to most-changing across call sites. Context and configuration come first; per-call data comes last.
```python
# GOOD - session/repo rarely change, filters change per call
def search_projects(
    self,
    session: Session,
    tenant_id: str,
    status: Optional[Status] = None,
    query: Optional[str] = None,
) -> list[ProjectSchema]:
    pass

# BAD - variable data mixed before stable context
def search_projects(
    self,
    query: Optional[str],
    session: Session,
    status: Optional[Status],
    tenant_id: str,
) -> list[ProjectSchema]:
    pass
```

### Dependency Injection Over Global State
```python
# GOOD - Dependency injection
class ProjectService:
    def __init__(self, session: Session):
        self._session = session
        self._repository = ProjectRepository(session)

# BAD - Global state
_global_session = None
class ProjectService:
    def do_something(self):
        _global_session.query(...)
```

## Logging

### Use f-strings, Never %s or %d
```python
# CORRECT
logger.info(f'Creating project: {project.name}')
logger.error(f'Failed to create project: {str(e)}')

# WRONG - loguru doesn't support this
logger.info('Creating project: %s', project.name)
```

## Imports

### Never Use "src." Prefix
```python
# CORRECT
from projects.services.project_service import ProjectService
from common.entities.base_entity import BaseEntity

# WRONG
from src.projects.services.project_service import ProjectService
```

## Pydantic V2

### Use Annotated Syntax
```python
# CORRECT - Pydantic V2
from typing import Annotated
from pydantic import Field

name: Annotated[str, Field(description='Project name')]

# Use ConfigDict, not class Config
model_config = ConfigDict(from_attributes=True)
```

## Datetime

### Always Use Timezone-Aware Datetimes
```python
# CORRECT
from datetime import datetime, timezone
now = datetime.now(timezone.utc)

# WRONG
now = datetime.now()  # Naive datetime
```

## Common Mistakes

1. Using `%s` in log messages instead of f-strings
2. Adding "src." prefix to imports
3. Using naive datetimes (without timezone)
4. Using old Pydantic V1 `class Config:` syntax
5. Deep nesting instead of early returns
6. Missing type hints
7. Functions doing too many things
8. Putting variable per-call parameters before stable context parameters
