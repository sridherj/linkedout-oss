# SPDX-License-Identifier: Apache-2.0
"""Benchmark reporter — generates markdown reports from scored results."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="cli")

_PROJECT_DIR = Path(__file__).parent.parent.parent.parent
_RESULTS_DIR = _PROJECT_DIR / "benchmarks" / "results"


def _load_results(results_dir: Path) -> dict[str, dict]:
    """Load per-query result data from a results directory."""
    data = {}
    for f in sorted(results_dir.glob("*.json")):
        with open(f) as fh:
            entry = json.load(fh)
        data[entry["id"]] = entry
    return data


def generate_report(
    scores: list[dict],
    results_dir: Path | None = None,
    baseline_scores: list[dict] | None = None,
) -> str:
    """Generate a markdown benchmark report.

    Args:
        scores: List of score dicts (id, score, reasoning).
        results_dir: Directory with per-query JSON results (for metadata).
        baseline_scores: Optional baseline scores for delta comparison.

    Returns:
        Markdown report string.
    """
    results_dir = results_dir or _RESULTS_DIR / "linkedout"
    results_data = _load_results(results_dir) if results_dir.exists() else {}

    baseline_map = {s["id"]: s for s in baseline_scores} if baseline_scores else {}

    # Group by persona
    personas: dict[str, list[dict]] = {}
    for s in sorted(scores, key=lambda x: x["id"]):
        qid = s["id"]
        persona = results_data.get(qid, {}).get("persona", qid.split("_")[0])
        personas.setdefault(persona, []).append(s)

    all_scores = [s["score"] for s in scores if s["score"] > 0]
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# LinkedOut Benchmark Report",
        f"",
        f"**Generated:** {timestamp}",
        f"**Queries scored:** {len(scores)}",
        f"",
    ]

    # Aggregate stats
    if all_scores:
        lines.extend([
            "## Aggregate Scores",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Mean | {mean(all_scores):.2f} |",
            f"| Median | {median(all_scores):.1f} |",
            f"| Min | {min(all_scores)} |",
            f"| Max | {max(all_scores)} |",
            f"| Queries scored | {len(all_scores)} |",
            f"| Parse failures | {len(scores) - len(all_scores)} |",
            "",
        ])

        if baseline_map:
            baseline_scores_list = [baseline_map[s["id"]]["score"] for s in scores if s["id"] in baseline_map and baseline_map[s["id"]]["score"] > 0]
            current_scores_list = [s["score"] for s in scores if s["id"] in baseline_map and s["score"] > 0 and baseline_map[s["id"]]["score"] > 0]
            if baseline_scores_list and current_scores_list:
                delta = mean(current_scores_list) - mean(baseline_scores_list)
                direction = "+" if delta > 0 else ""
                lines.extend([
                    "### Baseline Comparison",
                    "",
                    f"| Metric | Baseline | Current | Delta |",
                    f"|--------|----------|---------|-------|",
                    f"| Mean | {mean(baseline_scores_list):.2f} | {mean(current_scores_list):.2f} | {direction}{delta:.2f} |",
                    "",
                ])

    # Per-persona breakdown
    lines.extend(["## Per-Persona Scores", ""])
    for persona, persona_scores in sorted(personas.items()):
        p_scores = [s["score"] for s in persona_scores if s["score"] > 0]
        p_mean = mean(p_scores) if p_scores else 0
        lines.append(f"### {persona.upper()} (mean: {p_mean:.2f})")
        lines.append("")
        lines.append("| Query ID | Score | Delta | Reasoning |")
        lines.append("|----------|-------|-------|-----------|")

        for s in persona_scores:
            delta_str = ""
            if s["id"] in baseline_map and baseline_map[s["id"]]["score"] > 0 and s["score"] > 0:
                d = s["score"] - baseline_map[s["id"]]["score"]
                delta_str = f"+{d}" if d > 0 else str(d)

            reasoning = s.get("reasoning", "")[:100].replace("|", "\\|")
            lines.append(f"| {s['id']} | {s['score']} | {delta_str} | {reasoning} |")
        lines.append("")

    # Worst performing queries
    worst = sorted([s for s in scores if s["score"] > 0], key=lambda x: x["score"])[:5]
    if worst:
        lines.extend([
            "## Worst Performing Queries",
            "",
            "| Query ID | Score | Query | Reasoning |",
            "|----------|-------|-------|-----------|",
        ])
        for s in worst:
            query_text = results_data.get(s["id"], {}).get("query", "N/A")[:60].replace("|", "\\|")
            reasoning = s.get("reasoning", "")[:80].replace("|", "\\|")
            lines.append(f"| {s['id']} | {s['score']} | {query_text} | {reasoning} |")
        lines.append("")

    # Timing stats
    timings = [results_data[qid].get("elapsed_seconds", 0) for qid in results_data if results_data[qid].get("elapsed_seconds")]
    if timings:
        lines.extend([
            "## Timing",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Mean latency | {mean(timings):.1f}s |",
            f"| Median latency | {median(timings):.1f}s |",
            f"| Max latency | {max(timings):.1f}s |",
            f"| Total wall clock | {sum(timings):.0f}s |",
            "",
        ])

    return "\n".join(lines)


def save_report(report: str, output_file: Path | None = None) -> Path:
    """Save markdown report to file."""
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = _PROJECT_DIR / "benchmarks" / "results" / f"report_{timestamp}.md"

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        f.write(report)
    logger.info(f"Report saved to {output_file}")
    return output_file
