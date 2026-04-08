# SPDX-License-Identifier: Apache-2.0
"""Quantified readiness report for LinkedOut setup.

Produces a comprehensive readiness report that captures exact counts,
coverage percentages, configuration status, gaps, and next steps.
The report is both printed as a human-readable console summary and
persisted as JSON. This is the definitive "is setup complete?" artifact.

The readiness report must NEVER contain API keys, passwords, or LinkedIn
URLs. The config section only shows whether keys are configured (boolean),
not their values.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from linkedout.setup.logging_integration import get_setup_logger

# ── Version ────────────────────────────────────────────────────────
_LINKEDOUT_VERSION = "0.1.0"


@dataclass
class ReadinessReport:
    """Complete readiness report for the LinkedOut setup.

    Attributes:
        operation: Fixed to ``"setup-readiness"``.
        timestamp: ISO 8601 timestamp of report generation.
        linkedout_version: Current LinkedOut version string.
        counts: Raw counts from the database and filesystem.
        coverage: Computed coverage percentages.
        config: Configuration status (booleans, not values).
        skills: Per-platform skill installation status.
        gaps: List of identified data/config gaps.
        next_steps: Suggested user actions.
    """

    operation: str = "setup-readiness"
    timestamp: str = ""
    linkedout_version: str = _LINKEDOUT_VERSION
    counts: dict = field(default_factory=dict)
    coverage: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    skills: dict = field(default_factory=dict)
    gaps: list[dict] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize the report to a plain dict for JSON output."""
        return asdict(self)


def collect_readiness_data(db_url: str, data_dir: Path) -> dict:  # noqa: ARG001
    """Gather all counts from the database and config files.

    Queries the database via CLI subprocess calls and inspects the
    filesystem for configuration status. Returns a raw data dict
    that feeds into ``compute_coverage`` and ``detect_gaps``.

    Args:
        db_url: Database connection URL.
        data_dir: Root data directory (e.g., ``~/linkedout-data``).

    Returns:
        Dict with keys ``counts``, ``config``, and ``skills``.
    """
    log = get_setup_logger("readiness")
    data_dir = Path(data_dir).expanduser()

    counts = _query_db_counts(log)
    config = _check_config(data_dir, log)
    skills = _check_skills(log)

    return {
        "counts": counts,
        "config": config,
        "skills": skills,
    }


def compute_coverage(data: dict) -> dict:
    """Calculate coverage percentages from raw counts.

    Args:
        data: Dict returned by ``collect_readiness_data``.

    Returns:
        Dict with percentage fields like ``embedding_coverage_pct``.
    """
    counts = data["counts"]

    profiles = counts.get("profiles_loaded", 0)
    with_embeddings = counts.get("profiles_with_embeddings", 0)
    connections_total = counts.get("connections_total", 0)
    connections_with_affinity = counts.get("connections_with_affinity", 0)
    connections_matched = counts.get("connections_company_matched", 0)

    embedding_pct = (with_embeddings / profiles * 100) if profiles > 0 else 0.0
    affinity_pct = (
        (connections_with_affinity / connections_total * 100)
        if connections_total > 0
        else 0.0
    )
    company_match_pct = (
        (connections_matched / connections_total * 100)
        if connections_total > 0
        else 0.0
    )

    return {
        "embedding_coverage_pct": round(embedding_pct, 1),
        "affinity_coverage_pct": round(affinity_pct, 1),
        "company_match_pct": round(company_match_pct, 1),
    }


def detect_gaps(data: dict) -> list[dict]:
    """Identify gaps with actionable descriptions.

    Args:
        data: Dict returned by ``collect_readiness_data``.

    Returns:
        List of gap dicts, each with ``type``, ``count``, and ``detail``.
    """
    gaps: list[dict] = []
    counts = data["counts"]

    missing_embeddings = counts.get("profiles_without_embeddings", 0)
    if missing_embeddings > 0:
        gaps.append({
            "type": "missing_embeddings",
            "count": missing_embeddings,
            "detail": f"{missing_embeddings} profiles without embeddings",
        })

    missing_affinity = counts.get("connections_without_affinity", 0)
    if missing_affinity > 0:
        gaps.append({
            "type": "missing_affinity",
            "count": missing_affinity,
            "detail": f"{missing_affinity} connections without affinity scores",
        })

    missing_aliases = counts.get("companies_missing_aliases", 0)
    if missing_aliases > 0:
        gaps.append({
            "type": "missing_company_aliases",
            "count": missing_aliases,
            "detail": (
                f"{missing_aliases} companies without aliases "
                "(will resolve on next seed update)"
            ),
        })

    return gaps


def suggest_next_steps(gaps: list[dict]) -> list[str]:
    """Generate next steps based on identified gaps.

    Args:
        gaps: List of gap dicts from ``detect_gaps``.

    Returns:
        List of human-readable next-step strings.
    """
    steps: list[str] = []

    for gap in gaps:
        gap_type = gap["type"]
        count = gap["count"]
        if gap_type == "missing_embeddings":
            steps.append(
                f"Run `linkedout embed` to cover remaining {count} profiles"
            )
        elif gap_type == "missing_affinity":
            steps.append(
                f"Run `linkedout compute-affinity` to score {count} connections"
            )

    # Always suggest trying the tool
    steps.append('Try: /linkedout "who do I know at Stripe?"')
    steps.append('Try: /linkedout "find me warm intros to Series B AI startups"')

    if not any(g["type"] == "missing_embeddings" for g in gaps):
        steps.append(
            "Install the Chrome extension for passive profile enrichment"
        )

    return steps


def generate_readiness_report(db_url: str, data_dir: Path) -> ReadinessReport:
    """Generate the full readiness report.

    This is the main entry point that orchestrates data collection,
    coverage computation, gap detection, and next-step generation.

    Args:
        db_url: Database connection URL.
        data_dir: Root data directory.

    Returns:
        A complete ``ReadinessReport`` instance.
    """
    data = collect_readiness_data(db_url, data_dir)
    coverage = compute_coverage(data)
    gaps = detect_gaps(data)
    steps = suggest_next_steps(gaps)

    return ReadinessReport(
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        counts=data["counts"],
        coverage=coverage,
        config=data["config"],
        skills=data.get("skills", {}),
        gaps=gaps,
        next_steps=steps,
    )


def format_console_report(report: ReadinessReport) -> str:
    """Format the readiness report as human-readable console output.

    Uses the exact format from the UX design doc (Section 6) with
    box-drawing header, sectioned layout, and actionable gaps/next steps.

    Args:
        report: A ``ReadinessReport`` instance.

    Returns:
        Multi-line string ready for ``print()``.
    """
    counts = report.counts
    coverage = report.coverage
    config = report.config
    skills = report.skills

    profiles = counts.get("profiles_loaded", 0)
    with_emb = counts.get("profiles_with_embeddings", 0)
    companies = counts.get("companies_loaded", 0)
    conn_matched = counts.get("connections_company_matched", 0)
    conn_total = counts.get("connections_total", 0)
    conn_affinity = counts.get("connections_with_affinity", 0)

    lines: list[str] = []

    # Header
    lines.append("\u2554" + "\u2550" * 54 + "\u2557")
    lines.append("\u2551" + "LinkedOut Setup \u2014 Readiness".center(54) + "\u2551")
    lines.append("\u255a" + "\u2550" * 54 + "\u255d")
    lines.append("")

    # Data section
    lines.append("  Data")
    lines.append("  " + "\u2500" * 52)
    lines.append(f"  Profiles:        {profiles:,} loaded")
    lines.append(
        f"  Embeddings:      {with_emb:,} / {profiles:,} "
        f"({coverage.get('embedding_coverage_pct', 0):.1f}%)"
        if profiles > 0
        else "  Embeddings:      0 / 0"
    )
    lines.append(f"  Companies:       {companies:,} loaded")
    lines.append(
        f"  Company match:   {conn_matched:,} / {conn_total:,} connections "
        f"({coverage.get('company_match_pct', 0):.1f}%)"
        if conn_total > 0
        else "  Company match:   0 / 0 connections"
    )
    lines.append(
        f"  Affinity:        {conn_affinity:,} / {conn_total:,} connections "
        f"scored ({coverage.get('affinity_coverage_pct', 0):.1f}%)"
        if conn_total > 0
        else "  Affinity:        0 / 0 connections scored"
    )
    lines.append("")

    # Configuration section
    lines.append("  Configuration")
    lines.append("  " + "\u2500" * 52)
    emb_provider = config.get("embedding_provider", "unknown")
    data_dir_display = config.get("data_dir", "~/linkedout-data/")
    db_connected = config.get("db_connected", False)
    openai_configured = config.get("openai_key_configured", False)
    apify_configured = config.get("apify_key_configured", False)
    agent_env = config.get("agent_context_env_exists", False)

    lines.append(f"  Embedding:       {_format_provider(emb_provider)}")
    lines.append(f"  Data directory:  {data_dir_display}")
    lines.append(
        f"  Database:        {'connected' if db_connected else 'not connected'}"
    )
    lines.append(
        f"  OpenAI key:      {'configured' if openai_configured else 'not configured'}"
    )
    lines.append(
        f"  Apify key:       {'configured' if apify_configured else 'not configured'}"
    )
    if agent_env:
        lines.append(
            f"  Agent context:   {data_dir_display}config/agent-context.env"
        )
    lines.append("")

    # Skills section
    lines.append("  Skills")
    lines.append("  " + "\u2500" * 52)
    for platform_name, info in skills.items():
        installed = info.get("installed", False)
        skill_count = info.get("skill_count", 0)
        if installed:
            lines.append(
                f"  {platform_name:<17}installed ({skill_count} skills)"
            )
        else:
            lines.append(f"  {platform_name:<17}not detected")
    if not skills:
        lines.append("  No AI platforms detected")
    lines.append("")

    # Gaps or no-gaps message
    if report.gaps:
        lines.append("  Gaps")
        lines.append("  " + "\u2500" * 52)
        for gap in report.gaps:
            lines.append(f"  \u26a0 {gap['detail']}")
        lines.append("")

        lines.append("  Next Steps")
        lines.append("  " + "\u2500" * 52)
    else:
        lines.append("  No gaps found. Your network is fully indexed.")
        lines.append("")
        lines.append("  Get Started")
        lines.append("  " + "\u2500" * 52)

    for step in report.next_steps:
        lines.append(f"  \u2192 {step}")

    return "\n".join(lines)


def save_report(report: ReadinessReport, data_dir: Path) -> Path:
    """Persist the readiness report as JSON to the reports directory.

    Args:
        report: A ``ReadinessReport`` instance.
        data_dir: Root data directory (e.g., ``~/linkedout-data``).

    Returns:
        Path to the saved JSON file.
    """
    data_dir = Path(data_dir).expanduser()
    reports_dir = data_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.fromisoformat(report.timestamp.replace("Z", "+00:00"))
    filename = f"setup-readiness-{ts.strftime('%Y%m%d-%H%M%S')}.json"
    filepath = reports_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)

    return filepath


# ── Internal helpers ──────────────────────────────────────────────


def _format_provider(provider: str) -> str:
    """Format the embedding provider for display."""
    if provider == "openai":
        return "OpenAI (text-embedding-3-small)"
    if provider == "local":
        return "Local (nomic-embed-text-v1.5, 768d)"
    return provider


def _query_db_counts(log) -> dict:
    """Query database for all readiness counts via CLI diagnostics.

    Uses ``linkedout diagnostics --json`` to get counts. If the command
    is unavailable, falls back to individual queries.
    """
    counts = {
        "profiles_loaded": 0,
        "profiles_with_embeddings": 0,
        "profiles_without_embeddings": 0,
        "companies_loaded": 0,
        "companies_missing_aliases": 0,
        "role_aliases_loaded": 0,
        "connections_total": 0,
        "connections_with_affinity": 0,
        "connections_without_affinity": 0,
        "connections_company_matched": 0,
        "seed_tables_populated": 0,
    }

    result = subprocess.run(
        [sys.executable, "-m", "linkedout.commands", "diagnostics", "--json"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            # Map diagnostics output to our counts
            for key in counts:
                if key in data:
                    counts[key] = data[key]
            # Compute derived fields if not present
            if (
                counts["profiles_without_embeddings"] == 0
                and counts["profiles_loaded"] > 0
            ):
                counts["profiles_without_embeddings"] = (
                    counts["profiles_loaded"] - counts["profiles_with_embeddings"]
                )
            if (
                counts["connections_without_affinity"] == 0
                and counts["connections_total"] > 0
            ):
                counts["connections_without_affinity"] = (
                    counts["connections_total"] - counts["connections_with_affinity"]
                )
        except (json.JSONDecodeError, KeyError) as exc:
            log.warning("Failed to parse diagnostics JSON: {}", exc)
    else:
        log.warning(
            "diagnostics --json failed (exit {}), counts will be zero",
            result.returncode,
        )

    return counts


def _check_config(data_dir: Path, log) -> dict:
    """Check configuration file status."""
    config_dir = data_dir / "config"

    # Read embedding provider from config
    embedding_provider = "unknown"
    try:
        from shared.config import get_config

        cfg = get_config()
        embedding_provider = cfg.embedding.provider
    except Exception as exc:
        log.debug("Could not read config for provider: {}", exc)

    # Display data_dir with ~ shorthand
    try:
        data_dir_display = "~/" + str(data_dir.relative_to(Path.home())) + "/"
    except ValueError:
        data_dir_display = str(data_dir) + "/"

    return {
        "embedding_provider": embedding_provider,
        "data_dir": data_dir_display,
        "db_connected": _check_db_connected(),
        "openai_key_configured": bool(os.environ.get("OPENAI_API_KEY"))
        or (config_dir / "secrets.yaml").exists(),
        "apify_key_configured": bool(os.environ.get("APIFY_API_KEY")),
        "agent_context_env_exists": (config_dir / "agent-context.env").exists(),
    }


def _check_db_connected() -> bool:
    """Check if the database is reachable."""
    result = subprocess.run(
        [sys.executable, "-m", "linkedout.commands", "diagnostics", "--ping"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _check_skills(log) -> dict:  # noqa: ARG001
    """Check skill installation status per platform."""
    skills: dict = {}
    home = Path.home()

    platforms = {
        "Claude Code": home / ".claude" / "skills" / "linkedout",
        "Codex": home / ".agents" / "skills" / "linkedout",
        "Copilot": home / ".github" / "skills" / "linkedout",
    }

    for name, skill_dir in platforms.items():
        if skill_dir.exists():
            skill_files = list(skill_dir.glob("*/SKILL.md"))
            skills[name] = {
                "installed": len(skill_files) > 0,
                "skill_count": len(skill_files),
                "path": str(skill_dir),
            }
        else:
            # Check if platform is detected but skills not installed
            platform_dir = skill_dir.parent.parent.parent
            if platform_dir.exists():
                skills[name] = {
                    "installed": False,
                    "skill_count": 0,
                    "path": str(skill_dir),
                }

    return skills
