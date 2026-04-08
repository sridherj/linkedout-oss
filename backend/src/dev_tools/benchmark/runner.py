# SPDX-License-Identifier: Apache-2.0
"""Benchmark runner — executes queries against LinkedOut search and captures results."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="cli")

_SRC_DIR = Path(__file__).parent.parent.parent
_PROJECT_DIR = _SRC_DIR.parent
_QUERIES_DIR = _PROJECT_DIR / "benchmarks" / "queries"
_RESULTS_DIR = _PROJECT_DIR / "benchmarks" / "results"


def load_queries(pattern: str | None = None) -> list[dict]:
    """Load query definitions from YAML files, optionally filtered by glob pattern."""
    import fnmatch

    queries = []
    for yaml_file in sorted(_QUERIES_DIR.glob("*.yaml")):
        with open(yaml_file) as f:
            q = yaml.safe_load(f)
        if pattern and not fnmatch.fnmatch(q["id"], pattern):
            continue
        queries.append(q)
    return queries


def _set_rls_context(session, app_user_id: str) -> None:
    """Set RLS session variable so the user's rows are visible.

    Uses is_local=false so the setting persists across transaction boundaries
    within this session (important since SQLAlchemy may auto-commit between operations).
    """
    session.execute(
        text("SELECT set_config('app.current_user_id', :uid, false)"),
        {"uid": app_user_id},
    )


def _get_app_user_id(session) -> str:
    """Get the primary app_user_id (the one with most connections).

    Uses pg_stat to bypass RLS for discovery, then verifies with RLS context.
    """
    # First try direct query (works if RLS not enforced or user is superuser)
    result = session.execute(text(
        "SELECT app_user_id FROM connection "
        "GROUP BY app_user_id ORDER BY count(*) DESC LIMIT 1"
    )).scalar()
    if result:
        return result

    # RLS is blocking — query app_user table directly (no RLS on org tables)
    result = session.execute(text(
        "SELECT id FROM app_user ORDER BY created_at LIMIT 1"
    )).scalar()
    if not result:
        raise RuntimeError("No app_users found in database")
    return result


def _format_results_for_storage(response) -> list[dict]:
    """Extract key fields from SearchResponse results for storage."""
    formatted = []
    for r in response.results[:20]:
        formatted.append({
            "connection_id": r.connection_id,
            "crawled_profile_id": r.crawled_profile_id,
            "full_name": r.full_name,
            "headline": r.headline,
            "current_position": r.current_position,
            "current_company_name": r.current_company_name,
            "location_city": r.location_city,
            "location_country": r.location_country,
            "affinity_score": r.affinity_score,
            "dunbar_tier": r.dunbar_tier,
            "match_context": r.match_context,
        })
    return formatted


def run_linkedout_queries(
    queries: list[dict],
    output_dir: Path | None = None,
) -> list[dict]:
    """Run queries through LinkedOut SearchAgent and save per-query JSON results.

    Args:
        queries: List of query dicts (from load_queries).
        output_dir: Where to write per-query JSON. Defaults to benchmarks/results/linkedout/.

    Returns:
        List of result dicts with scores, timing, etc.
    """
    import sys
    sys.path.insert(0, str(_SRC_DIR))

    from shared.config import get_config

    output_dir = output_dir or _RESULTS_DIR / "linkedout"
    output_dir.mkdir(parents=True, exist_ok=True)

    db_url = get_config().database_url
    engine = create_engine(db_url, echo=False)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    # Get app_user_id
    init_session = Session()
    app_user_id = _get_app_user_id(init_session)
    init_session.close()
    logger.info(f"Using app_user_id: {app_user_id}")

    from linkedout.intelligence.agents.search_agent import SearchAgent

    all_results = []

    for q in queries:
        logger.info(f"Running [{q['id']}]: {q['query'][:60]}...")

        # Fresh session per query to avoid poisoned transaction state
        query_session = Session()
        _set_rls_context(query_session, app_user_id)
        agent = SearchAgent(session=query_session, app_user_id=app_user_id)

        start = time.time()
        try:
            response = agent.run(q["query"], limit=20)
            elapsed = time.time() - start

            entry = {
                "id": q["id"],
                "persona": q["persona"],
                "query": q["query"],
                "dimensions": q.get("dimensions", []),
                "difficulty": q.get("difficulty", "unknown"),
                "expected_behavior": q.get("expected_behavior", ""),
                "answer": response.answer,
                "query_type": response.query_type,
                "result_count": response.result_count,
                "results": _format_results_for_storage(response),
                "app_user_id": app_user_id,
                "elapsed_seconds": round(elapsed, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            logger.info(f"  -> {response.result_count} results, type={response.query_type}, {elapsed:.1f}s")

        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"  -> FAILED: {e}")
            entry = {
                "id": q["id"],
                "persona": q["persona"],
                "query": q["query"],
                "dimensions": q.get("dimensions", []),
                "difficulty": q.get("difficulty", "unknown"),
                "expected_behavior": q.get("expected_behavior", ""),
                "answer": None,
                "query_type": None,
                "result_count": 0,
                "results": [],
                "app_user_id": app_user_id,
                "elapsed_seconds": round(elapsed, 2),
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            query_session.close()

        # Save per-query result
        result_file = output_dir / f"{q['id']}.json"
        with open(result_file, "w") as f:
            json.dump(entry, f, indent=2, default=str)

        all_results.append(entry)

    engine.dispose()
    return all_results


def run_claude_code_queries(
    queries: list[dict],
    output_dir: Path | None = None,
) -> list[dict]:
    """Run queries through Claude Code (claude -p) with DB access for gold standard capture.

    Each query is run as an independent Claude Code subprocess that can query the DB directly.
    """
    import subprocess

    from shared.config import get_config

    output_dir = output_dir or _RESULTS_DIR / "claude_code"
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt_template = """You are searching a LinkedIn network database for the user. Answer this query:

"{query}"

DB connection: DATABASE_URL is configured via config.yaml / env var.

CRITICAL — RLS is enabled. Every psql command must chain set_config with your query:
psql "$DATABASE_URL" -c "SELECT set_config('app.current_user_id', '{app_user_id}', false); <YOUR QUERY>;"

Use ILIKE (not LOWER+LIKE) for text searches — trigram GIN indexes exist on headline, current_company_name, current_position, company_name, position, skill_name, school_name. Always JOIN through connection (app_user_id = '{app_user_id}') to scope to the user's network.

Key tables: crawled_profile, connection, experience, education, company, company_alias, profile_skill. Connection links crawled_profile to app_user via app_user_id.

Find the most relevant people and explain why they match. Return your answer as a numbered list of people with: name, current role, company, and why they match the query."""

    # Get app_user_id for RLS context
    db_url = get_config().database_url
    if db_url:
        engine = create_engine(db_url, echo=False)
        _Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        init_session = _Session()
        app_user_id = _get_app_user_id(init_session)
        init_session.close()
        engine.dispose()
    else:
        app_user_id = "usr_sys_001"

    all_results = []

    for q in queries:
        logger.info(f"Claude Code [{q['id']}]: {q['query'][:60]}...")
        result_file = output_dir / f"{q['id']}.json"

        # Skip if already captured
        if result_file.exists():
            logger.info(f"  -> already captured, skipping")
            with open(result_file) as f:
                all_results.append(json.load(f))
            continue

        prompt = prompt_template.format(query=q["query"], app_user_id=app_user_id)
        start = time.time()

        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--model", "opus", "--dangerously-skip-permissions"],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(_PROJECT_DIR),
            )
            elapsed = time.time() - start

            entry = {
                "id": q["id"],
                "persona": q["persona"],
                "query": q["query"],
                "answer": result.stdout.strip(),
                "elapsed_seconds": round(elapsed, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "claude_code",
            }
            logger.info(f"  -> captured in {elapsed:.1f}s")

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            entry = {
                "id": q["id"],
                "persona": q["persona"],
                "query": q["query"],
                "answer": None,
                "error": "Timed out (300s)",
                "elapsed_seconds": round(elapsed, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "claude_code",
            }
            logger.error(f"  -> timed out")

        except Exception as e:
            elapsed = time.time() - start
            entry = {
                "id": q["id"],
                "persona": q["persona"],
                "query": q["query"],
                "answer": None,
                "error": str(e),
                "elapsed_seconds": round(elapsed, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "claude_code",
            }
            logger.error(f"  -> failed: {e}")

        with open(result_file, "w") as f:
            json.dump(entry, f, indent=2, default=str)
        all_results.append(entry)

    return all_results
