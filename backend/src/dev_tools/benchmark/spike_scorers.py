# SPDX-License-Identifier: Apache-2.0
"""LLM-as-judge scorers for the benchmark spike: custom prompt-based + Opus-with-DB-access."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="cli")

OUTPUT_DIR = src_path.parent / "benchmarks" / "spike"

# ── Rubric (shared by all scorers) ────────────────────────────────────────────

RUBRIC = """Score 1-5 based on how well the search results answer the user's query:

5 - Excellent: Results directly answer the query. Right people, right reasoning, no noise. Would trust this for a real decision.
4 - Good: Mostly right — key results present but minor gaps (missed a few relevant people, or included some borderline matches).
3 - Partial: Gets the gist but significant issues — missing an important segment, or reasoning is shallow (e.g., matched on keyword not career trajectory).
2 - Poor: Some relevant results by accident, but fundamentally misunderstood the query intent or used wrong approach.
1 - Failed: Empty results, hallucinated data, completely wrong interpretation, or returned irrelevant people.

Score on three dimensions holistically:
- Result relevance: did it find the right people?
- Reasoning quality: did it understand the intent (e.g., "climbing fast" = rapid title progression)?
- Completeness: did it miss an obvious segment it should have caught?"""


# ── Scorer 1: Custom prompt-based (GPT-4o as judge) ─────────────────────────

CUSTOM_JUDGE_PROMPT = """You are an expert evaluator of professional network search quality.

A user searched their LinkedIn network with the following query. Review the search results and the system's answer, then score the quality.

## Query
{query}

## What this query tests
{tests}

## System's Answer
{answer}

## Results returned ({result_count} total, showing up to 20)
{results_formatted}

## Scoring Rubric
{rubric}

## Instructions
1. Analyze how well the results and answer address the user's actual intent
2. Consider whether the system understood implicit requirements
3. Provide your score and reasoning

Respond in this exact JSON format:
{{"score": <1-5>, "reasoning": "<2-3 sentences explaining your score>"}}"""


def format_results_for_judge(results: list[dict]) -> str:
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


def run_custom_scorer(results_file: Path | None = None) -> list[dict]:
    """Score all spike results using OpenAI GPT-4o as judge."""
    from openai import OpenAI

    results_file = results_file or OUTPUT_DIR / "spike_results.json"
    with open(results_file) as f:
        all_results = json.load(f)

    client = OpenAI()
    scores = []

    for entry in all_results:
        if entry.get("error"):
            scores.append({"id": entry["id"], "score": 1, "reasoning": f"Query failed: {entry['error']}", "scorer": "custom"})
            continue

        prompt = CUSTOM_JUDGE_PROMPT.format(
            query=entry["query"],
            tests=entry["tests"],
            answer=entry["answer"][:2000] if entry["answer"] else "(no answer)",
            result_count=entry["result_count"],
            results_formatted=format_results_for_judge(entry["results"]),
            rubric=RUBRIC,
        )

        logger.info(f"Custom scoring [{entry['id']}]: {entry['query'][:50]}...")
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        text_response = response.choices[0].message.content or ""
        try:
            match = re.search(r'\{[^}]+\}', text_response, re.DOTALL)
            parsed = json.loads(match.group()) if match else {"score": 0, "reasoning": text_response}
            scores.append({
                "id": entry["id"],
                "score": int(parsed["score"]),
                "reasoning": parsed.get("reasoning", ""),
                "scorer": "custom",
            })
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            logger.error(f"Failed to parse custom score for {entry['id']}: {e}")
            scores.append({"id": entry["id"], "score": 0, "reasoning": f"Parse error: {text_response[:200]}", "scorer": "custom"})

    output_file = OUTPUT_DIR / "spike_scores_custom.json"
    with open(output_file, "w") as f:
        json.dump(scores, f, indent=2)
    logger.info(f"Custom scores saved to {output_file}")
    return scores


# ── Scorer 2: Claude Code Opus (subprocess with DB access) ───────────────────

OPUS_JUDGE_PROMPT = """You are evaluating the quality of a LinkedIn network search engine.

A user queried their network. The SearchAgent returned results. Your job: verify whether the results are actually correct by querying the database yourself, then score.

## User's Query
{query}

## What this query tests
{tests}

## SearchAgent's Answer
{answer}

## Results returned ({result_count} total, showing top {shown})
{results_formatted}

## Scoring Rubric
{rubric}

## Instructions
1. Use /postgres or run SQL via Bash to query the database and verify the results. The database has tables: crawled_profile, connection, experience, education, company, company_alias, profile_skill. Connection table links crawled_profile to app_user via app_user_id.
2. Check: did the search find the RIGHT people? Did it miss obvious candidates? Did it understand the query intent?
3. For completeness checks, query the DB for profiles the system may have missed.

After your investigation, output ONLY this JSON on the last line — no other text after it:
{{"score": <1-5>, "reasoning": "<2-3 sentences explaining your score>"}}"""


def run_opus_judge_scorer(
    results_file: Path | None = None,
) -> list[dict]:
    """Score spike results by spawning Claude Code Opus sessions with DB access.

    Each query is scored by an independent `claude -p` subprocess running Opus,
    which can query the database directly to verify claims before scoring.
    """
    import subprocess

    results_file = results_file or OUTPUT_DIR / "spike_results.json"
    with open(results_file) as f:
        all_results = json.load(f)

    scores = []
    project_dir = str(src_path.parent)

    for entry in all_results:
        if entry.get("error"):
            scores.append({
                "id": entry["id"],
                "score": 1,
                "reasoning": f"Query failed: {entry['error']}",
                "scorer": "opus_with_db",
            })
            continue

        prompt = OPUS_JUDGE_PROMPT.format(
            query=entry["query"],
            tests=entry["tests"],
            answer=entry["answer"][:2000] if entry["answer"] else "(no answer)",
            result_count=entry["result_count"],
            shown=min(len(entry["results"]), 20),
            results_formatted=format_results_for_judge(entry["results"]),
            rubric=RUBRIC,
        )

        logger.info(f"Opus scoring [{entry['id']}]: {entry['query'][:50]}...")

        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--model", "sonnet"],
                capture_output=True,
                text=True,
                timeout=180,
                cwd=project_dir,
            )

            stdout = result.stdout.strip()
            # Extract JSON from the last line or anywhere in output
            score_entry = _parse_judge_output(entry["id"], stdout)

        except subprocess.TimeoutExpired:
            logger.error(f"Opus judge timed out for {entry['id']}")
            score_entry = {
                "id": entry["id"],
                "score": 0,
                "reasoning": "Claude Code subprocess timed out (180s)",
                "scorer": "opus_with_db",
            }
        except Exception as e:
            logger.error(f"Opus judge failed for {entry['id']}: {e}")
            score_entry = {
                "id": entry["id"],
                "score": 0,
                "reasoning": f"Subprocess error: {str(e)[:200]}",
                "scorer": "opus_with_db",
            }

        logger.info(f"  -> score={score_entry['score']}")
        scores.append(score_entry)

    output_file = OUTPUT_DIR / "spike_scores_opus.json"
    with open(output_file, "w") as f:
        json.dump(scores, f, indent=2)
    logger.info(f"Opus scores saved to {output_file}")
    return scores


def _parse_judge_output(query_id: str, stdout: str) -> dict:
    """Extract score JSON from Claude Code subprocess output."""
    # Try last line first (expected location), then search full output
    for text in [stdout.rsplit("\n", 1)[-1], stdout]:
        match = re.search(r'\{"score":\s*\d.*?\}', text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
                return {
                    "id": query_id,
                    "score": int(parsed["score"]),
                    "reasoning": parsed.get("reasoning", ""),
                    "scorer": "opus_with_db",
                }
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

    logger.error(f"Could not parse score from Opus output for {query_id}: {stdout[-300:]}")
    return {
        "id": query_id,
        "score": 0,
        "reasoning": f"Parse error from output: {stdout[-200:]}",
        "scorer": "opus_with_db",
    }


# ── Correlation calculator ────────────────────────────────────────────────────

def calculate_correlation(
    gold_scores: dict[str, int],
    *additional_scorers: list[dict],
    scorer_names: list[str] | None = None,
) -> dict:
    """Calculate Spearman correlation between gold standard and one or more scorers.

    Args:
        gold_scores: dict of {query_id: score} (ground truth)
        *additional_scorers: lists of score dicts from run_*_scorer()
        scorer_names: labels for each scorer (defaults to scorer0, scorer1, ...)
    """
    from scipy.stats import spearmanr

    query_ids = sorted(gold_scores.keys())
    gold_vals = [gold_scores[qid] for qid in query_ids]
    names = scorer_names or [f"scorer{i}" for i in range(len(additional_scorers))]

    correlations = {}
    score_comparison = [{
        "id": qid,
        "gold": gold_scores[qid],
    } for qid in query_ids]

    for name, scorer_results in zip(names, additional_scorers):
        score_map = {s["id"]: s["score"] for s in scorer_results}
        scorer_vals = [score_map.get(qid, 0) for qid in query_ids]
        sr = spearmanr(gold_vals, scorer_vals)
        corr: float = float(sr[0])  # type: ignore[index]
        p_val: float = float(sr[1])  # type: ignore[index]

        correlations[name] = {
            "spearman_rho": round(corr, 3),
            "p_value": round(p_val, 4),
            "verdict": "green-light" if corr > 0.7 else ("needs-work" if corr > 0.5 else "different-approach"),
            "mean_absolute_error": round(sum(abs(g - s) for g, s in zip(gold_vals, scorer_vals)) / len(query_ids), 2),
            "mean_bias": round(sum(s - g for g, s in zip(gold_vals, scorer_vals)) / len(query_ids), 2),
        }
        for row in score_comparison:
            row[name] = score_map.get(row["id"], 0)

    return {
        "query_count": len(query_ids),
        "correlations": correlations,
        "score_comparison": score_comparison,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--scorer", choices=["custom", "opus", "both"], default="opus")
    parser.add_argument("--results-file", type=Path, default=None)
    args = parser.parse_args()

    if args.scorer in ("custom", "both"):
        run_custom_scorer(args.results_file)
    if args.scorer in ("opus", "both"):
        run_opus_judge_scorer(args.results_file)
