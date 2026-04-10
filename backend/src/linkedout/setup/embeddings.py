# SPDX-License-Identifier: Apache-2.0
"""Embedding generation orchestration for LinkedOut setup.

Wraps the existing ``linkedout embed`` CLI command with setup-specific UX:
time/cost estimates, confirmation prompts, progress tracking, and result
summaries. All operations are idempotent — only profiles without embeddings
are processed, and interruptions can be resumed.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from linkedout.setup.logging_integration import get_setup_logger
from shared.utilities.operation_report import OperationCounts, OperationReport

# ── Prompt text (exact wording from setup-flow-ux.md) ────────────────

_PROMPT_OPENAI = """\
Step 11 of 15: Embedding Generation

  Profiles needing embeddings: {count:,}
  Provider: OpenAI (text-embedding-3-small, Batch API)
  Estimated time: {time_estimate}
  Estimated cost: {cost_estimate} (one-time, via Batch API)

  Generate embeddings now? [Y/n] """

_PROMPT_LOCAL = """\
Step 11 of 15: Embedding Generation

  Profiles needing embeddings: {count:,}
  Provider: Local (nomic-embed-text-v1.5, 768 dimensions)
  Model size: ~275 MB (will download if not cached)
  Estimated time: {time_estimate}
  Cost: Free

  Generate embeddings now? [Y/n] """


def count_profiles_needing_embeddings(db_url: str) -> int:  # noqa: ARG001
    """Count enriched profiles that lack embeddings.

    Delegates to ``linkedout embed --dry-run`` which reads the DB URL
    from config. The *db_url* parameter is accepted for interface
    consistency with other setup modules.

    Args:
        db_url: Database connection URL (for interface consistency).

    Returns:
        Number of profiles that need embedding generation.
    """
    log = get_setup_logger("embeddings")

    result = subprocess.run(
        ["linkedout", "embed", "--dry-run"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        log.warning("embed --dry-run failed, defaulting to 0: {}", result.stderr.strip())
        return 0

    # Parse "Profiles needing embedding: N" from dry-run output
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if "needing embedding" in stripped.lower():
            # Extract the number: "Profiles needing embedding: 4,012"
            parts = stripped.split(":")
            if len(parts) >= 2:
                count_str = parts[-1].strip().replace(",", "")
                try:
                    return int(count_str)
                except ValueError:
                    pass

    log.warning("Could not parse profile count from embed --dry-run output")
    return 0


def estimate_embedding_time(count: int, provider: str) -> str:
    """Return a human-readable time estimate for embedding *count* profiles.

    Uses conservative estimates that overestimate rather than underestimate.

    Args:
        count: Number of profiles to embed.
        provider: ``"openai"`` or ``"local"``.

    Returns:
        Human-readable time string (e.g., ``"~2-3 minutes"``).
    """
    if provider == "openai":
        # OpenAI Batch API: ~2-3 minutes for 4K profiles, scales roughly linearly
        if count <= 500:
            return "~1-2 minutes"
        if count <= 2000:
            return "~2-3 minutes"
        if count <= 5000:
            return "~3-5 minutes"
        if count <= 10000:
            return "~5-10 minutes"
        minutes = count // 1000
        return f"~{minutes}-{minutes + 5} minutes"
    else:
        # Local nomic: ~0.2s per profile on CPU (conservative)
        seconds = count * 0.2
        if seconds < 60:
            return "~1 minute"
        minutes = int(seconds / 60)
        if minutes <= 5:
            return f"~{minutes}-{minutes + 2} minutes"
        if minutes <= 15:
            return f"~{minutes}-{minutes + 5} minutes (depends on CPU)"
        return f"~{minutes}-{minutes + 10} minutes (depends on CPU)"


def estimate_embedding_cost(count: int, provider: str) -> str | None:
    """Return a human-readable cost estimate, or ``None`` if free.

    Uses current OpenAI Batch API pricing for text-embedding-3-small:
    $0.01 per 1M tokens, with Batch API 50% discount. Average profile
    text is ~200 tokens.

    Args:
        count: Number of profiles to embed.
        provider: ``"openai"`` or ``"local"``.

    Returns:
        Cost string like ``"~$0.04"`` for OpenAI, or ``None`` for local.
    """
    if provider == "local":
        return None

    # OpenAI text-embedding-3-small: ~$0.02 per 1M tokens
    # Batch API: 50% discount -> ~$0.01 per 1M tokens
    # Average profile ~200 tokens -> 200K tokens per 1K profiles
    # Cost per 1K profiles: 200K/1M * $0.01 = ~$0.002
    # But we advertise ~$0.01 per 1K profiles as conservative estimate
    cost = count * 0.00001  # $0.01 per 1K profiles
    if cost < 0.01:
        return "~$0.01"
    return f"~${cost:.2f}"


def run_embeddings(provider: str) -> OperationReport:
    """Execute embedding generation via the ``linkedout embed`` CLI.

    Runs ``linkedout embed --provider <provider>`` as a subprocess.
    The CLI command handles progress bars, resumability, and search
    vector population.

    Args:
        provider: ``"openai"`` or ``"local"``.

    Returns:
        OperationReport summarizing the embedding result.

    Raises:
        RuntimeError: If the embed command fails.
    """
    log = get_setup_logger("embeddings")
    start = time.monotonic()

    print(f"  Generating embeddings with {provider} provider...")

    cmd = ["linkedout", "embed", "--provider", provider]

    result = subprocess.run(cmd, capture_output=True, text=True)
    duration_ms = (time.monotonic() - start) * 1000

    if result.returncode != 0:
        log.error("embed failed: {}", result.stderr.strip())
        error_output = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"linkedout embed failed (exit code {result.returncode}):\n"
            f"  {error_output}\n\n"
            f"  Progress is saved automatically. Run `linkedout embed` to resume.\n"
            f"  Use `linkedout embed --dry-run` to check what remains."
        )

    stdout = result.stdout.strip()
    if stdout:
        print(stdout)

    # Parse counts from output if possible
    embedded = 0
    for line in (result.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("Embedded:"):
            count_str = stripped.split(":")[1].strip().split()[0].replace(",", "")
            try:
                embedded = int(count_str)
            except ValueError:
                pass

    log.info("Embedding generation completed in {:.1f}s", duration_ms / 1000)

    return OperationReport(
        operation="setup-embeddings",
        duration_ms=duration_ms,
        counts=OperationCounts(total=embedded, succeeded=embedded),
        next_steps=["Run `linkedout compute-affinity` to compute affinity scores"],
    )


def setup_embeddings(data_dir: Path, db_url: str) -> OperationReport:  # noqa: ARG001
    """Full embedding generation orchestration for the setup flow.

    Steps:
    1. Count profiles needing embeddings
    2. Read provider from config
    3. Show time/cost estimates
    4. Ask for confirmation
    5. Run embedding generation

    Args:
        data_dir: Root data directory (e.g., ``~/linkedout-data``).
        db_url: Database connection URL.

    Returns:
        OperationReport summarizing what was done.
    """
    start = time.monotonic()

    # Read provider from config
    from shared.config import get_config
    cfg = get_config()
    provider = cfg.embedding.provider

    # Count profiles
    count = count_profiles_needing_embeddings(db_url)

    if count == 0:
        print("Step 11 of 15: Embedding Generation\n")
        print("  All profiles already have embeddings. Nothing to do.")
        duration_ms = (time.monotonic() - start) * 1000
        return OperationReport(
            operation="setup-embeddings",
            duration_ms=duration_ms,
            counts=OperationCounts(total=0, succeeded=0),
        )

    # Build estimates
    time_estimate = estimate_embedding_time(count, provider)
    cost_estimate = estimate_embedding_cost(count, provider)

    # Show prompt with estimates
    if provider == "openai":
        prompt = _PROMPT_OPENAI.format(
            count=count,
            time_estimate=time_estimate,
            cost_estimate=cost_estimate or "Free",
        )
    else:
        prompt = _PROMPT_LOCAL.format(
            count=count,
            time_estimate=time_estimate,
        )

    try:
        choice = input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        choice = ""  # default to yes (generate embeddings)
    if choice in ("n", "no"):
        print("\n  Skipping embedding generation.")
        print("  You can run it later: linkedout embed")
        duration_ms = (time.monotonic() - start) * 1000
        return OperationReport(
            operation="setup-embeddings",
            duration_ms=duration_ms,
            counts=OperationCounts(total=0, succeeded=0, skipped=count),
            next_steps=["Run `linkedout embed` to generate embeddings"],
        )

    # Run embeddings
    report = run_embeddings(provider)

    # Show completion
    print(f"\n  Embedding generation complete.")

    duration_ms = (time.monotonic() - start) * 1000
    return OperationReport(
        operation="setup-embeddings",
        duration_ms=duration_ms,
        counts=report.counts,
        next_steps=report.next_steps,
    )
