# SPDX-License-Identifier: Apache-2.0
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
    check_has_answer: bool = False
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
        category="company_type",
    ),
    EvalQuery(
        query="Product company engineers",
        expected_min_results=20,
        expected_query_type="sql",
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
        category="company_type",
    ),

    # === Career Transitions (5) ===
    EvalQuery(
        query="Moved from IT services to product companies",
        expected_min_results=40,
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
        query="Career changers -- engineering to non-engineering",
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
        expected_min_results=0,
        expected_query_type="sql",
        check_has_answer=True,
        category="aggregation",
    ),
    EvalQuery(
        query="Top companies in my network by connection count",
        expected_min_results=0,
        expected_query_type="sql",
        check_has_answer=True,
        category="aggregation",
    ),
]
