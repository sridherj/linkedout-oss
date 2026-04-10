# Sub-Phase 6: Eval Framework (Phase 5)

**Working directory:** `./`
**Depends on:** Nothing (can run in parallel with sub-phases 4 and 5)
**Creates:**
- `tests/eval/__init__.py`
- `tests/eval/conftest.py`
- `tests/eval/search_eval_queries.py`
- `tests/eval/test_search_quality.py`

## Context

There is no automated way to evaluate search quality. This sub-phase creates a 30-query eval framework that runs against the real DB and checks result quality.

## Review Decisions

- **Arch-3:** Use `integration-test-creator-agent` for scaffolding (conftest, fixtures, DB wiring) only. Hand-write the eval-specific logic.
- **Tests-2:** Use range assertions for ground truth counts, not exact numbers (data changes over time).

## Tasks

### 5a. Create eval query definitions

**File:** `tests/eval/search_eval_queries.py`

```python
"""Search quality evaluation query definitions."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class EvalQuery:
    """A single evaluation query with expected outcomes."""
    query: str
    expected_min_results: int
    expected_query_type: str  # sql | vector | hybrid
    must_include_names: list[str] = field(default_factory=list)
    company_pattern: str | None = None  # Regex that N% of results must match
    no_hallucination: bool = True
    category: str = ""


EVAL_QUERIES: list[EvalQuery] = [
    # === Name Lookup (3) ===
    EvalQuery(
        query="Find Agil C",
        expected_min_results=1,
        expected_query_type="sql",
        must_include_names=["Agil C"],
        category="name_lookup",
    ),
    EvalQuery(
        query="Who is Karthik Viswanathan",
        expected_min_results=1,
        expected_query_type="sql",
        must_include_names=["Karthik Viswanathan"],
        category="name_lookup",
    ),
    EvalQuery(
        query="Priya",
        expected_min_results=3,
        expected_query_type="sql",
        category="name_lookup",
    ),

    # === Company-Specific (4) ===
    EvalQuery(
        query="Engineers at Google",
        expected_min_results=50,
        expected_query_type="sql",
        category="company_specific",
    ),
    EvalQuery(
        query="People at Infosys",
        expected_min_results=100,
        expected_query_type="sql",
        category="company_specific",
    ),
    EvalQuery(
        query="Who works at Flipkart right now",
        expected_min_results=5,
        expected_query_type="sql",
        category="company_specific",
    ),
    EvalQuery(
        query="People from Crio.Do",
        expected_min_results=50,
        expected_query_type="sql",
        category="company_specific",
    ),

    # === Company-Type (4) ===
    EvalQuery(
        query="People at IT services companies",
        expected_min_results=20,
        expected_query_type="sql",
        company_pattern=r"(?i)(tcs|infosys|wipro|cognizant|tata|accenture)",
        category="company_type",
    ),
    EvalQuery(
        query="Product company engineers",
        expected_min_results=20,
        expected_query_type="sql",
        company_pattern=r"(?i)(google|amazon|microsoft|meta|flipkart)",
        category="company_type",
    ),
    EvalQuery(
        query="People at FAANG companies",
        expected_min_results=20,
        expected_query_type="sql",
        category="company_type",
    ),
    EvalQuery(
        query="Who's at consulting firms",
        expected_min_results=10,
        expected_query_type="sql",
        company_pattern=r"(?i)(deloitte|mckinsey|accenture|boston consulting|bain)",
        category="company_type",
    ),

    # === Career Transitions (5) ===
    EvalQuery(
        query="Moved from IT services to product companies",
        expected_min_results=50,
        expected_query_type="sql",
        category="career_transition",
    ),
    EvalQuery(
        query="Engineering to product management transition",
        expected_min_results=5,
        expected_query_type="sql",
        category="career_transition",
    ),
    EvalQuery(
        query="People who left Google in last 2 years",
        expected_min_results=5,
        expected_query_type="sql",
        category="career_transition",
    ),
    EvalQuery(
        query="Recently joined startups",
        expected_min_results=5,
        expected_query_type="hybrid",
        category="career_transition",
    ),
    EvalQuery(
        query="Career changers — engineering to non-engineering",
        expected_min_results=5,
        expected_query_type="hybrid",
        category="career_transition",
    ),

    # === Skills-Based (3) ===
    EvalQuery(
        query="People who know Python and React",
        expected_min_results=50,
        expected_query_type="sql",
        category="skills",
    ),
    EvalQuery(
        query="Machine learning experts",
        expected_min_results=20,
        expected_query_type="sql",
        category="skills",
    ),
    EvalQuery(
        query="Full stack developers with AWS experience",
        expected_min_results=10,
        expected_query_type="sql",
        category="skills",
    ),

    # === Location (3) ===
    EvalQuery(
        query="Engineers in Bangalore",
        expected_min_results=50,
        expected_query_type="sql",
        category="location",
    ),
    EvalQuery(
        query="Connections in the US",
        expected_min_results=20,
        expected_query_type="sql",
        category="location",
    ),
    EvalQuery(
        query="People in London",
        expected_min_results=5,
        expected_query_type="sql",
        category="location",
    ),

    # === Seniority (3) ===
    EvalQuery(
        query="Senior engineers",
        expected_min_results=50,
        expected_query_type="sql",
        category="seniority",
    ),
    EvalQuery(
        query="Founders in my network",
        expected_min_results=50,
        expected_query_type="sql",
        category="seniority",
    ),
    EvalQuery(
        query="Directors and VPs",
        expected_min_results=30,
        expected_query_type="sql",
        category="seniority",
    ),

    # === Semantic/Concept (3) ===
    EvalQuery(
        query="People working on AI agents",
        expected_min_results=5,
        expected_query_type="vector",
        category="semantic",
    ),
    EvalQuery(
        query="Climate tech founders",
        expected_min_results=1,
        expected_query_type="vector",
        category="semantic",
    ),
    EvalQuery(
        query="People interested in open source",
        expected_min_results=5,
        expected_query_type="vector",
        category="semantic",
    ),

    # === Aggregation (2) ===
    EvalQuery(
        query="How many connections by country",
        expected_min_results=1,
        expected_query_type="sql",
        category="aggregation",
    ),
    EvalQuery(
        query="Top companies in my network by connection count",
        expected_min_results=1,
        expected_query_type="sql",
        category="aggregation",
    ),
]
```

### 5b. Create eval test runner

**File:** `tests/eval/test_search_quality.py`

```python
"""Search quality evaluation test runner.

Run with: pytest tests/eval/ -m eval -v
Excluded from regular test runs via pytest marker.
"""
from __future__ import annotations

import re
import pytest

from tests.eval.search_eval_queries import EVAL_QUERIES, EvalQuery

# Mark all tests in this module as eval (excluded from regular runs)
pytestmark = pytest.mark.eval


@pytest.fixture(scope="module")
def search_agent(db_session, app_user_id):
    """Create a SearchAgent instance for eval queries."""
    from linkedout.intelligence.agents.search_agent import SearchAgent
    return SearchAgent(session=db_session, app_user_id=app_user_id)


@pytest.mark.parametrize(
    "eval_query",
    EVAL_QUERIES,
    ids=[q.query[:50] for q in EVAL_QUERIES],
)
def test_search_quality(search_agent, eval_query: EvalQuery):
    """Run a single eval query and check results against expectations."""
    from linkedout.intelligence.contracts import SearchRequest

    request = SearchRequest(query=eval_query.query, limit=100)
    response = search_agent.run(request)

    # Check minimum result count
    assert response.result_count >= eval_query.expected_min_results, (
        f"Query '{eval_query.query}' returned {response.result_count} results, "
        f"expected >= {eval_query.expected_min_results}"
    )

    # Check must-include names
    result_names = {r.full_name for r in response.results}
    for name in eval_query.must_include_names:
        assert any(name.lower() in rn.lower() for rn in result_names), (
            f"Expected '{name}' in results for query '{eval_query.query}'"
        )

    # Check company pattern (if specified, at least 30% of results should match)
    if eval_query.company_pattern and response.results:
        pattern = re.compile(eval_query.company_pattern)
        matching = sum(
            1 for r in response.results
            if r.current_company_name and pattern.search(r.current_company_name)
        )
        match_pct = matching / len(response.results)
        assert match_pct >= 0.3, (
            f"Only {match_pct:.0%} of results matched company pattern "
            f"'{eval_query.company_pattern}' for query '{eval_query.query}'"
        )
```

### 5c. Create conftest for eval tests

**File:** `tests/eval/conftest.py`

Check how existing integration tests set up DB sessions and app_user_id fixtures. Look at:
- `tests/conftest.py`
- `tests/integration/conftest.py`

Reuse the same patterns. The eval conftest needs:
- `db_session` fixture (real DB connection)
- `app_user_id` fixture (SJ's user ID)

If these are already defined in a parent conftest, you may not need a separate conftest.

### 5d. Register eval marker

**File:** `pyproject.toml` or `pytest.ini` (wherever markers are registered)

Add:
```ini
[tool.pytest.ini_options]
markers = [
    "eval: Search quality evaluation tests (run with -m eval)",
]
```

Also ensure eval tests are excluded from default runs by adding to the default `addopts` or `testpaths` config:
```ini
addopts = "-m 'not eval'"
```

Or if there's already an `addopts`, append the marker filter.

## Verification

1. `pytest tests/eval/search_eval_queries.py --collect-only` — should find 30 tests
2. `pytest tests/eval/ -m eval -v --co` — should list all eval queries
3. `pytest tests/ -x -q --timeout=30` — regular tests should NOT include eval tests
4. Run one eval query manually: `pytest tests/eval/ -m eval -k "Find Agil C" -v`
