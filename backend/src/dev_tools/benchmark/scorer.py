# SPDX-License-Identifier: Apache-2.0
"""Production benchmark scorer — LLM-as-judge via Claude subprocess with DB access.

Design informed by spike validation (Spearman rho=0.739 for subprocess approach).
Each query scored by an independent `claude -p --model sonnet` session that compares
results against the Claude Code gold standard and verifies via database queries.
"""
from __future__ import annotations

import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="cli")

_PROJECT_DIR = Path(__file__).parent.parent.parent.parent
_GOLD_STANDARD_DIR = _PROJECT_DIR / "benchmarks" / "results" / "claude_code"

RUBRIC = """Score 1-5 based on how well the search results answer the user's query:

5 - Excellent: Results directly answer the query. Right people, right reasoning, no noise.
4 - Good: Mostly right — key results present but minor gaps.
3 - Partial: Gets the gist but significant issues — missing an important segment, shallow reasoning.
2 - Poor: Some relevant results by accident, but fundamentally misunderstood the query.
1 - Failed: Empty results, hallucinated data, completely wrong interpretation.

Score holistically on:
- Result relevance: did it find the right people?
- Reasoning quality: did it understand the intent?
- Completeness: did it miss an obvious segment?"""

JUDGE_PROMPT = """FIRST, run this exact command to enable database access (RLS is enabled, without this ALL queries return 0 rows):

psql "$DATABASE_URL" -c "SELECT set_config('app.current_user_id', '{app_user_id}', false);"

Now proceed with the evaluation.

You are evaluating a LinkedIn network search engine's quality by comparing it against a gold standard.

A user queried their network. The SearchAgent returned results. A Claude Code session with direct DB access previously answered the same query — this is the gold standard. Your job: compare the SearchAgent's results against the gold standard, verify key claims via database queries, then score.

IMPORTANT: Every psql command must start with: psql "$DATABASE_URL" -c "SELECT set_config('app.current_user_id', '{app_user_id}', false); <your query here>"
Chain set_config with your query in the same -c string so they share the same session.

## User's Query
{query}

## What this query tests
{expected_behavior}

## Dimensions being evaluated
{dimensions}

## Gold Standard (Claude Code with direct DB access)
{gold_standard}

## SearchAgent's Answer
{answer}

## Results returned ({result_count} total, showing top {shown})
{results_formatted}

## Scoring Rubric
{rubric}

## Instructions
1. Compare the SearchAgent's results against the gold standard. The gold standard represents what's achievable with direct DB access — it's the ceiling.
2. Use database queries to verify specific claims when needed: psql "$DATABASE_URL" -c "SELECT set_config('app.current_user_id', '{app_user_id}', false); <YOUR QUERY>;" Key tables: crawled_profile, connection, experience, education, company, company_alias, profile_skill. Connection links crawled_profile to app_user via app_user_id. Use ILIKE for text searches (trigram GIN indexes exist).
3. Score based on: How many of the gold standard's key people did the SearchAgent find? Did it miss important segments? Did it understand the query intent as well as the gold standard?
4. A score of 5 means the SearchAgent matched or exceeded the gold standard. A score of 1 means it completely missed.

After investigation, output ONLY this JSON on the very last line:
{{"score": <1-5>, "reasoning": "<2-3 sentences explaining your score>"}}"""

JUDGE_PROMPT_NO_GOLD = """FIRST, run this exact command to enable database access (RLS is enabled, without this ALL queries return 0 rows):

psql "$DATABASE_URL" -c "SELECT set_config('app.current_user_id', '{app_user_id}', false);"

Now proceed with the evaluation.

You are evaluating a LinkedIn network search engine's quality.

A user queried their network. The SearchAgent returned results. Your job: verify whether the results are correct by querying the database yourself, then score.

IMPORTANT: Every psql command must start with: psql "$DATABASE_URL" -c "SELECT set_config('app.current_user_id', '{app_user_id}', false); <your query here>"
Chain set_config with your query in the same -c string so they share the same session.

## User's Query
{query}

## What this query tests
{expected_behavior}

## Dimensions being evaluated
{dimensions}

## SearchAgent's Answer
{answer}

## Results returned ({result_count} total, showing top {shown})
{results_formatted}

## Scoring Rubric
{rubric}

## Instructions
1. Query the database using: psql "$DATABASE_URL" -c "SELECT set_config('app.current_user_id', '{app_user_id}', false); <YOUR QUERY>;" Key tables: crawled_profile, connection, experience, education, company, company_alias, profile_skill. Connection links crawled_profile to app_user via app_user_id. Use ILIKE for text searches (trigram GIN indexes exist).
2. Check: did the search find the RIGHT people? Did it miss obvious candidates? Did it understand the query intent?
3. For completeness, query the DB for profiles the system may have missed.

After investigation, output ONLY this JSON on the very last line:
{{"score": <1-5>, "reasoning": "<2-3 sentences explaining your score>"}}"""


def _format_results(results: list[dict]) -> str:
    """Format search results for the judge prompt."""
    if not results:
        return "(no results returned)"
    lines = []
    for i, r in enumerate(results, 1):
        parts = [f"{i}. {r.get('full_name', 'Unknown')}"]
        if r.get("headline"):
            parts.append(f"   Headline: {r['headline']}")
        if r.get("current_position") or r.get("current_company_name"):
            pos = r.get("current_position", "")
            co = r.get("current_company_name", "")
            parts.append(f"   Current: {pos} at {co}".strip())
        if r.get("location_city") or r.get("location_country"):
            loc = f"{r.get('location_city', '')}, {r.get('location_country', '')}".strip(", ")
            parts.append(f"   Location: {loc}")
        if r.get("affinity_score") is not None:
            parts.append(f"   Affinity: {r['affinity_score']}")
        if r.get("match_context"):
            ctx = {k: v for k, v in r["match_context"].items() if v is not None}
            if ctx:
                parts.append(f"   Match context: {json.dumps(ctx)}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


def _parse_judge_output(query_id: str, stdout: str) -> dict:
    """Extract score JSON from Claude subprocess output."""
    for text in [stdout.rsplit("\n", 1)[-1], stdout]:
        match = re.search(r'\{"score":\s*\d.*?\}', text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
                return {
                    "id": query_id,
                    "score": int(parsed["score"]),
                    "reasoning": parsed.get("reasoning", ""),
                }
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

    logger.error(f"Could not parse score for {query_id}: {stdout[-300:]}")
    return {
        "id": query_id,
        "score": 0,
        "reasoning": f"Parse error: {stdout[-200:]}",
    }


def _load_gold_standard(query_id: str) -> str | None:
    """Load Claude Code gold standard answer for a query, if available."""
    gold_file = _GOLD_STANDARD_DIR / f"{query_id}.json"
    if not gold_file.exists():
        return None
    with open(gold_file) as f:
        data = json.load(f)
    answer = data.get("answer")
    if not answer:
        return None
    # Handle dict answers (structured output from some captures)
    if isinstance(answer, dict):
        answer = json.dumps(answer, indent=2, default=str)
    # Truncate to keep prompt reasonable
    return str(answer)[:3000]


def score_single(query_id: str, result_data: dict) -> dict:
    """Score a single query result via Claude subprocess.

    Uses Claude Code gold standard as reference when available, falls back to
    independent DB verification otherwise.

    Args:
        query_id: The query ID.
        result_data: The result dict from runner (must have query, answer, results, etc.).

    Returns:
        Score dict with id, score, reasoning.
    """
    if result_data.get("error"):
        return {
            "id": query_id,
            "score": 1,
            "reasoning": f"Query failed: {result_data['error']}",
        }

    results = result_data.get("results", [])
    gold_standard = _load_gold_standard(query_id)

    if gold_standard:
        prompt = JUDGE_PROMPT.format(
            query=result_data["query"],
            expected_behavior=result_data.get("expected_behavior", "N/A"),
            dimensions=", ".join(result_data.get("dimensions", [])),
            gold_standard=gold_standard,
            answer=(result_data.get("answer") or "(no answer)")[:2000],
            result_count=result_data.get("result_count", 0),
            shown=min(len(results), 20),
            results_formatted=_format_results(results),
            rubric=RUBRIC,
            app_user_id=result_data.get("app_user_id", "usr_sys_001"),
        )
    else:
        prompt = JUDGE_PROMPT_NO_GOLD.format(
            query=result_data["query"],
            expected_behavior=result_data.get("expected_behavior", "N/A"),
            dimensions=", ".join(result_data.get("dimensions", [])),
            answer=(result_data.get("answer") or "(no answer)")[:2000],
            result_count=result_data.get("result_count", 0),
            shown=min(len(results), 20),
            results_formatted=_format_results(results),
            rubric=RUBRIC,
            app_user_id=result_data.get("app_user_id", "usr_sys_001"),
        )

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", "sonnet", "--dangerously-skip-permissions"],
            capture_output=True,
            text=True,
            timeout=1000,
            cwd=str(_PROJECT_DIR),
        )
        return _parse_judge_output(query_id, result.stdout.strip())

    except subprocess.TimeoutExpired:
        logger.error(f"Judge timed out for {query_id}")
        return {"id": query_id, "score": 0, "reasoning": "Judge subprocess timed out (1000s)"}

    except Exception as e:
        logger.error(f"Judge failed for {query_id}: {e}")
        return {"id": query_id, "score": 0, "reasoning": f"Subprocess error: {str(e)[:200]}"}


def score_all(
    results_dir: Path,
    max_parallel: int = 4,
) -> list[dict]:
    """Score all query results in a directory, with parallelism.

    Args:
        results_dir: Directory containing per-query JSON result files.
        max_parallel: Number of concurrent scorer subprocesses.

    Returns:
        List of score dicts sorted by query ID.
    """
    result_files = sorted(results_dir.glob("*.json"))
    if not result_files:
        logger.warning(f"No result files found in {results_dir}")
        return []

    # Load all results
    result_data_map: dict[str, dict] = {}
    for f in result_files:
        with open(f) as fh:
            data = json.load(fh)
        result_data_map[data["id"]] = data

    gold_count = sum(1 for qid in result_data_map if _load_gold_standard(qid) is not None)
    logger.info(
        f"Scoring {len(result_data_map)} queries with {max_parallel} parallel judges "
        f"({gold_count} with gold standard, {len(result_data_map) - gold_count} DB-only)"
    )

    scores = []
    with ThreadPoolExecutor(max_workers=max_parallel) as executor:
        futures = {
            executor.submit(score_single, qid, data): qid
            for qid, data in result_data_map.items()
        }
        for future in as_completed(futures):
            qid = futures[future]
            try:
                score = future.result()
                logger.info(f"  [{qid}] score={score['score']}")
                scores.append(score)
            except Exception as e:
                logger.error(f"  [{qid}] scorer exception: {e}")
                scores.append({"id": qid, "score": 0, "reasoning": f"Exception: {e}"})

    return sorted(scores, key=lambda s: s["id"])


def save_scores(scores: list[dict], output_file: Path) -> None:
    """Save scores to a JSON file."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(scores, f, indent=2)
    logger.info(f"Scores saved to {output_file}")
