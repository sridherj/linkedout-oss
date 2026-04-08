# SPDX-License-Identifier: Apache-2.0
"""CLI entry point for the LinkedOut benchmark suite.

Usage:
    python -m dev_tools.benchmark run [--compare baseline] [--queries sj_*] [--report-only]
    python -m dev_tools.benchmark run --capture-claude-code
    python -m dev_tools.benchmark run --capture-baseline
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).parent.parent.parent
_PROJECT_DIR = _SRC_DIR.parent
_RESULTS_DIR = _PROJECT_DIR / "benchmarks" / "results"
_SCORES_DIR = _PROJECT_DIR / "benchmarks" / "scores"

sys.path.insert(0, str(_SRC_DIR))

from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="cli")


def cmd_run(args: argparse.Namespace) -> None:
    """Run benchmark: execute queries, score, and generate report."""
    from dev_tools.benchmark.runner import load_queries, run_claude_code_queries, run_linkedout_queries
    from dev_tools.benchmark.reporter import generate_report, save_report
    from dev_tools.benchmark.scorer import save_scores, score_all

    queries = load_queries(pattern=args.queries)
    if not queries:
        logger.error("No queries found matching pattern")
        sys.exit(1)

    logger.info(f"Loaded {len(queries)} queries")

    # Capture Claude Code gold standard
    if args.capture_claude_code:
        logger.info("==> Capturing Claude Code gold standard results...")
        run_claude_code_queries(queries)
        logger.info("==> Claude Code capture complete")
        return

    # Capture baseline
    if args.capture_baseline:
        logger.info("==> Capturing LinkedOut baseline results...")
        baseline_dir = _RESULTS_DIR / "linkedout_baseline"
        run_linkedout_queries(queries, output_dir=baseline_dir)
        logger.info("==> Baseline capture complete")
        return

    results_dir = _RESULTS_DIR / "linkedout"

    # Run queries (unless --report-only)
    if not args.report_only:
        logger.info("==> Running LinkedOut queries...")
        run_linkedout_queries(queries, output_dir=results_dir)

    # Check results exist
    result_files = list(results_dir.glob("*.json"))
    if not result_files:
        logger.error(f"No results found in {results_dir}. Run queries first.")
        sys.exit(1)

    # Score (unless --report-only with existing scores)
    scores_file = _SCORES_DIR / "linkedout_scores.json"

    if not args.report_only:
        logger.info("==> Scoring results...")
        scores = score_all(results_dir, max_parallel=args.parallel)
        save_scores(scores, scores_file)
    else:
        if scores_file.exists():
            with open(scores_file) as f:
                scores = json.load(f)
            logger.info(f"Loaded {len(scores)} existing scores")
        else:
            logger.info("No existing scores found, scoring now...")
            scores = score_all(results_dir, max_parallel=args.parallel)
            save_scores(scores, scores_file)

    # Load baseline scores for comparison
    baseline_scores = None
    if args.compare:
        baseline_file = _SCORES_DIR / f"{args.compare}_scores.json"
        if baseline_file.exists():
            with open(baseline_file) as f:
                baseline_scores = json.load(f)
            logger.info(f"Loaded baseline scores from {baseline_file}")
        else:
            logger.warning(f"Baseline scores file not found: {baseline_file}")

    # Generate report
    logger.info("==> Generating report...")
    report = generate_report(
        scores=scores,
        results_dir=results_dir,
        baseline_scores=baseline_scores,
    )
    report_path = save_report(report)
    print(f"\n{report}")
    print(f"\nReport saved to: {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dev_tools.benchmark",
        description="LinkedOut search quality benchmark suite",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run command
    run_parser = subparsers.add_parser("run", help="Run benchmark queries, score, and report")
    run_parser.add_argument("--queries", type=str, default=None, help="Glob pattern to filter queries (e.g., 'sj_*')")
    run_parser.add_argument("--compare", type=str, default=None, help="Compare against named baseline (e.g., 'baseline')")
    run_parser.add_argument("--report-only", action="store_true", help="Skip execution, generate report from existing results")
    run_parser.add_argument("--capture-claude-code", action="store_true", help="Capture Claude Code gold standard results")
    run_parser.add_argument("--capture-baseline", action="store_true", help="Capture LinkedOut baseline results")
    run_parser.add_argument("--parallel", type=int, default=4, help="Number of parallel scorer processes (default: 4)")
    run_parser.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
