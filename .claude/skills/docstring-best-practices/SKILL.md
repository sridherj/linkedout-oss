---
name: docstring-best-practices
user_invocable: true
description: Apply docstring standards when writing or reviewing Python functions and classes. Use when creating new classes, functions, or methods to ensure proper documentation with description, args, returns, and exceptions.
---

# DocStringBestPractices Skill

Apply these docstring standards when writing or reviewing Python code.

## Reference
- `./reference_code/.cursor/rules/bestpractices.mdc`
- Google Python Style Guide: https://google.github.io/styleguide/pyguide.html

## Docstring Structure

Every function/method must have a docstring with:

```python
def function_name(arg1: str, arg2: int) -> ReturnType:
    """
    Short one-line description of what the function does.

    Longer description if needed. Include:
    - What the function does
    - Any assumptions the function makes
    - Important logic details
    - If the logic contains multiple steps, number them like 1, 2, 3. You can even use 1.1, 1.2 for sub-steps. Also make sure the function comments also mimic these numbered steps.
    - If an illustration makes it more easy to understand, include that. Lot of times, I expect devs to only read this instead of actual code. So make it thorough.
    
    Args:
        arg1: Description of arg1. Include any constraints or valid values.
        arg2: Description of arg2. Note if it can be None or has defaults.

    Returns:
        Description of what is returned.
        - Note corner cases: "Returns None if entity not found"
        - Note if can return empty: "Returns empty list if no matches"
        If return value is a dictionary, mention what is the key and what is the value clearly

    Raises:
        ValueError: When validation fails (describe when)
        HTTPException: When entity not found (describe when)
    """
```

## Examples

### Service Method
```python
def get_project_by_id(self, request: GetProjectByIdRequestSchema) -> Optional[ProjectSchema]:
    """
    Retrieve a project by its unique identifier.

    Fetches the project from the database using the provided tenant, workspace,
    and project IDs. The project must belong to the specified tenant and workspace.

    Args:
        request: Request schema containing tenant_id, workspace_id, and project_id.
            All three IDs are required and will be validated.

    Returns:
        ProjectSchema if found, None if the project doesn't exist.
        The schema contains all project fields including timestamps.

    Raises:
        AssertionError: If tenant_id, workspace_id, or project_id is missing.
    """
```

### Repository Method
```python
def list_with_filters(
    self,
    tenant_id: str,
    workspace_id: str,
    limit: int = 20,
    offset: int = 0,
    status: Optional[List[str]] = None,
) -> List[ProjectEntity]:
    """
    Retrieve a paginated list of projects with optional filtering.

    Queries the database for projects belonging to the specified tenant and
    workspace. Results can be filtered by status and paginated.

    Args:
        tenant_id: ID of the tenant. Must not be None.
        workspace_id: ID of the workspace. Must not be None.
        limit: Maximum number of results to return (default: 20, max: 100).
        offset: Number of results to skip for pagination (default: 0).
        status: Optional list of status values to filter by. If empty or None,
            no status filter is applied.

    Returns:
        List of ProjectEntity objects matching the criteria. May be empty if
        no projects match. Ordered by created_at descending by default.
    """
```

### Class Docstring
```python
class ProjectService:
    """
    Service layer for Project business logic.

    Handles all business operations for projects including CRUD operations,
    validation, and orchestration of repository calls. This service:
    - Receives request schemas from controllers
    - Returns response schemas (never exposes entities)
    - Delegates to ProjectRepository for database operations

    Attributes:
        _session: SQLAlchemy session for database operations.
        _project_repository: Repository for project data access.
    """
```

## Key Rules

1. **Always include**: Description, Args, Returns
2. **Include Raises when applicable**: Document exceptions that can be raised
3. **Document corner cases**: Empty returns, None returns, edge cases
4. **Document constraints**: Valid values, required fields, limits
5. **Use imperative mood**: "Retrieve a project" not "Retrieves a project"
6. **Keep first line short**: Under 80 characters, summarizes the function
7. **Docstrings are source of truth**: Docstrings for most parts are source of truth of what needs to be done. Implementation/tests are all fixed based on this - so pay attention. It is sacrosanct!

## Common Mistakes

1. Missing Returns section
2. Not documenting when None can be returned
3. Not documenting when empty list can be returned
4. Missing Raises section for functions that raise exceptions
5. Vague descriptions like "Process the data"
6. Missing Args section
