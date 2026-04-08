# SPDX-License-Identifier: Apache-2.0
"""Run all test suites before committing.

Usage:
    precommit-tests                   # unit + integration (default)
    precommit-tests --suite unit
    precommit-tests --suite integration
    precommit-tests --suite installation
    precommit-tests --suite skills
    precommit-tests --suite live_llm
    precommit-tests --suite live_services
    precommit-tests -m "not slow"     # extra pytest marker filter
    precommit-tests -x                # stop after first suite failure
    precommit-tests --all             # include live suites
"""
import subprocess
import sys
import time
from pathlib import Path

import click

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # backend/
REPO_ROOT = PROJECT_ROOT.parent                                # repo root

SUITES = [
    {
        "name": "unit",
        "label": "Unit tests",
        "args": [
            "pytest", "tests/", "-q", "--tb=short",
            "--override-ini=addopts=",
            "-n", "auto", "--dist=loadfile",
            "-m", "not integration and not live_llm and not live_langfuse and not eval",
        ],
    },
    {
        "name": "integration",
        "label": "Integration tests (PostgreSQL)",
        "args": [
            "pytest", "tests/integration/", "-q", "--tb=short",
            "--override-ini=addopts=",
            "-m", "integration",
        ],
    },
    {
        "name": "installation",
        "label": "Installation flow tests",
        "args": [
            "pytest", "tests/installation/", "-v", "--tb=short",
            "--override-ini=addopts=",
        ],
        "cwd": "repo",
        "live_only": True,
    },
    {
        "name": "skills",
        "label": "Skill template tests",
        "args": [
            "pytest", "tests/skills/", "-v", "--tb=short",
            "--override-ini=addopts=",
        ],
        "cwd": "repo",
        "live_only": True,
    },
    {
        "name": "live_llm",
        "label": "Live LLM tests",
        "args": [
            "pytest", "-q", "--tb=short",
            "--override-ini=addopts=",
            "-m", "live_llm",
        ],
        "live_only": True,
    },
    {
        "name": "live_services",
        "label": "Live service tests (Apify, etc.)",
        "args": [
            "pytest", "-q", "--tb=short",
            "--override-ini=addopts=",
            "-m", "live_services",
        ],
        "live_only": True,
    },
]

SUITE_NAMES = [s["name"] for s in SUITES if not s.get("live_only")]
ALL_SUITE_NAMES = [s["name"] for s in SUITES]


def run_suite(suite: dict, extra_args: list[str] | None = None) -> tuple[bool, float]:
    """Run a single suite. Returns (passed, duration_seconds)."""
    cmd = [sys.executable, "-m"] + suite["args"]
    if extra_args:
        cmd.extend(extra_args)

    click.echo()
    click.secho("=" * 60, fg="cyan")
    click.secho(f"  {suite['label']}", fg="cyan", bold=True)
    click.echo(f"  $ {' '.join(suite['args'])}")
    click.secho("=" * 60, fg="cyan")
    click.echo()

    cwd = REPO_ROOT if suite.get("cwd") == "repo" else PROJECT_ROOT

    start = time.time()
    result = subprocess.run(cmd, cwd=cwd)
    duration = time.time() - start

    return result.returncode == 0, duration


@click.command(name="precommit-tests")
@click.option(
    "--suite", "-s",
    type=click.Choice(ALL_SUITE_NAMES),
    help="Run only this suite.",
)
@click.option(
    "-m", "--marker",
    help="Extra pytest marker expression appended to the suite's default.",
)
@click.option(
    "--failfast", "-x",
    is_flag=True,
    help="Stop after the first suite failure.",
)
@click.option(
    "--all", "run_all",
    is_flag=True,
    help="Include live_llm suite (excluded by default).",
)
def precommit_tests(suite, marker, failfast, run_all):
    """Run test suites before pushing. Default: unit + integration."""
    extra_args = []
    if marker:
        extra_args.extend(["-m", marker])

    if suite:
        suites_to_run = [s for s in SUITES if s["name"] == suite]
    elif run_all:
        suites_to_run = SUITES
    else:
        suites_to_run = [s for s in SUITES if not s.get("live_only")]

    results: list[tuple[str, str, bool, float]] = []
    for s in suites_to_run:
        passed, duration = run_suite(s, extra_args)
        results.append((s["name"], s["label"], passed, duration))
        if not passed and failfast:
            break

    # Summary
    click.echo()
    click.secho("=" * 60, bold=True)
    click.secho("  RESULTS", bold=True)
    click.secho("=" * 60, bold=True)

    total = 0.0
    all_passed = True
    for name, label, passed, duration in results:
        total += duration
        if passed:
            click.secho(f"  [+] {label:<38} PASS  ({duration:.1f}s)", fg="green")
        else:
            click.secho(f"  [X] {label:<38} FAIL  ({duration:.1f}s)", fg="red")
            all_passed = False

    click.echo(f"\n  Total: {total:.1f}s")

    if all_passed:
        click.secho("\n  All suites passed!\n", fg="green", bold=True)
    else:
        failed = [name for name, _, passed, _ in results if not passed]
        click.secho(f"\n  Failed: {', '.join(failed)}", fg="red")
        click.echo(f"  Re-run: precommit-tests --suite {failed[0]}\n")
        sys.exit(1)


@click.command(name="eval-tests")
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show individual test names as they run.",
)
@click.option(
    "-k", "--keyword",
    help="Only run eval tests whose names match this expression.",
)
def eval_tests(verbose, keyword):
    """Run search quality eval tests against the real database.

    Requires DATABASE_URL pointing at a populated PostgreSQL instance.
    """
    args = [
        "pytest", "tests/eval/", "--tb=short",
        "--override-ini=addopts=",
        "-m", "eval",
        "-v" if verbose else "-q",
    ]
    if keyword:
        args.extend(["-k", keyword])

    suite = {"name": "eval", "label": "Eval tests (search quality)", "args": args}
    passed, duration = run_suite(suite)

    click.echo()
    click.secho("=" * 60, bold=True)
    if passed:
        click.secho(f"  [+] Eval tests  PASS  ({duration:.1f}s)", fg="green")
        click.secho("\n  All eval tests passed!\n", fg="green", bold=True)
    else:
        click.secho(f"  [X] Eval tests  FAIL  ({duration:.1f}s)", fg="red")
        click.echo("\n  Re-run: eval-tests\n")
        sys.exit(1)


if __name__ == "__main__":
    precommit_tests()
