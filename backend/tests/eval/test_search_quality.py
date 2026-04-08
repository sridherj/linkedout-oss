# SPDX-License-Identifier: Apache-2.0
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
    response = search_agent.run(request.query, limit=request.limit)

    # For aggregation queries, check the answer text rather than result count
    if eval_query.check_has_answer:
        assert response.answer and len(response.answer.strip()) > 0, (
            f"Query '{eval_query.query}' returned an empty answer"
        )
        return

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
