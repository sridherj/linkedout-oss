# SPDX-License-Identifier: Apache-2.0
"""Run spike queries through SearchAgent, save results as JSON for scoring."""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Setup path
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

from shared.config import get_config
from dev_tools.benchmark.spike_queries import SPIKE_QUERIES
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="cli")

OUTPUT_DIR = src_path.parent / "benchmarks" / "spike"


def get_db_session():
    db_url = get_config().database_url
    engine = create_engine(db_url, echo=False)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return Session(), engine


def get_app_user_id(session) -> str:
    result = session.execute(text(
        "SELECT app_user_id FROM connection "
        "GROUP BY app_user_id ORDER BY count(*) DESC LIMIT 1"
    )).scalar()
    if not result:
        raise RuntimeError("No app_users with connections found")
    return result


def format_results_for_scoring(response) -> list[dict]:
    """Extract key fields from results for human/LLM review."""
    formatted = []
    for r in response.results[:20]:  # Cap at 20 for readability
        formatted.append({
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


def run_all_queries():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    db_url = get_config().database_url
    engine = create_engine(db_url, echo=False)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    init_session = Session()
    app_user_id = get_app_user_id(init_session)
    init_session.close()
    logger.info(f"Using app_user_id: {app_user_id}")

    from linkedout.intelligence.agents.search_agent import SearchAgent

    all_results = []

    for q in SPIKE_QUERIES:
        logger.info(f"Running query [{q['id']}]: {q['query']}")

        # Fresh session per query to avoid poisoned transaction state
        query_session = Session()
        query_agent = SearchAgent(session=query_session, app_user_id=app_user_id)

        start = time.time()
        try:
            response = query_agent.run(q["query"], limit=20)
            elapsed = time.time() - start

            entry = {
                "id": q["id"],
                "persona": q["persona"],
                "query": q["query"],
                "tests": q["tests"],
                "answer": response.answer,
                "query_type": response.query_type,
                "result_count": response.result_count,
                "results": format_results_for_scoring(response),
                "elapsed_seconds": round(elapsed, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            all_results.append(entry)
            logger.info(
                f"  -> {response.result_count} results, "
                f"type={response.query_type}, {elapsed:.1f}s"
            )
        except Exception as e:
            logger.error(f"  -> FAILED: {e}")
            all_results.append({
                "id": q["id"],
                "persona": q["persona"],
                "query": q["query"],
                "tests": q["tests"],
                "answer": None,
                "query_type": None,
                "result_count": 0,
                "results": [],
                "elapsed_seconds": 0,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        finally:
            query_session.close()

    # Save raw results
    output_file = OUTPUT_DIR / "spike_results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    logger.info(f"Results saved to {output_file}")

    engine.dispose()
    return all_results


if __name__ == "__main__":
    run_all_queries()
