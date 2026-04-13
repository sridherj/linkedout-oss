# SPDX-License-Identifier: Apache-2.0
"""``linkedout enrich`` — enrich unenriched LinkedIn profiles via Apify.

Queries ``crawled_profile`` rows that lack enrichment data, dispatches batched
async enrichment via the Apify LinkedIn scraper, and processes results into
relational data. Supports ``--dry-run`` for cost estimation, ``--limit`` for
partial runs, and ``--skip-embeddings`` to defer embedding generation.
"""
import time
from pathlib import Path

import click
from sqlalchemy import text

from dev_tools.db.fixed_data import SYSTEM_USER_ID
from linkedout.cli_helpers import cli_logged
from linkedout.enrichment_pipeline.apify_client import get_platform_apify_key
from linkedout.enrichment_pipeline.bulk_enrichment import (
    check_recoverable_batches,
    recover_incomplete_batches,
)
from linkedout.enrichment_pipeline.post_enrichment import PostEnrichmentService
from shared.config import get_config
from shared.infra.db.cli_db import cli_db_manager
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger
from shared.utilities.metrics import record_metric
from shared.utilities.operation_report import OperationCounts, OperationReport

logger = get_logger(__name__, component="cli", operation="enrich")


def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs:.0f}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


def _build_next_steps(skip_embeddings: bool) -> list[str]:
    """Build next-steps list based on whether embeddings were skipped."""
    steps = []
    if skip_embeddings:
        steps.append("Run `linkedout embed` to generate embeddings for semantic search")
    steps.append("Run `linkedout compute-affinity` to calculate affinity scores")
    return steps


@click.command('enrich')
@click.option('--limit', type=int, default=None,
              help='Max profiles to enrich (default: all unenriched)')
@click.option('--dry-run', is_flag=True,
              help='Count unenriched profiles, estimate cost, exit without calling Apify')
@click.option('--skip-embeddings', is_flag=True,
              help='Skip embedding generation (can be done later with `linkedout embed`)')
@cli_logged("enrich")
def enrich_command(limit: int | None, dry_run: bool, skip_embeddings: bool):
    """Enrich unenriched LinkedIn profiles via Apify."""
    db_manager = cli_db_manager()
    cfg = get_config()
    cost_per = cfg.enrichment.cost_per_profile_usd
    start_time = time.time()

    # 1. Query unenriched profiles
    with db_manager.get_session(DbSessionType.READ, app_user_id=SYSTEM_USER_ID) as session:
        rows = session.execute(text(
            "SELECT id, linkedin_url FROM crawled_profile "
            "WHERE has_enriched_data = false "
            "AND linkedin_url LIKE '%linkedin.com/%'"
        )).fetchall()

    profiles = [(r[0], r[1]) for r in rows]
    total_unenriched = len(profiles)

    if total_unenriched == 0:
        click.echo("All profiles are enriched. Nothing to do.")
        return

    # Apply limit
    if limit is not None:
        profiles = profiles[:limit]
    total = len(profiles)

    # 2. Check for recoverable batches from prior incomplete runs
    data_dir = Path(cfg.data_dir)
    recovery_check = check_recoverable_batches(data_dir)
    recoverable = recovery_check.recovered  # profiles with SUCCEEDED Apify runs

    # 3. Dry-run
    if dry_run:
        click.echo(f"Dry run: {total_unenriched:,} unenriched profiles found")
        if recoverable > 0:
            click.echo(f"  {recoverable:,} have completed Apify runs awaiting collection (no additional cost)")
            new_cost = (total_unenriched - recoverable) * cost_per
            click.echo(f"  {total_unenriched - recoverable:,} need new Apify enrichment (~${new_cost:.2f})")
        else:
            est_cost = total_unenriched * cost_per
            click.echo(f"Estimated cost: ${est_cost:.2f} (~${cost_per * 1000:.2f} per 1,000 profiles)")
        if recovery_check.still_running > 0:
            click.echo(f"  {recovery_check.still_running:,} in batches still running on Apify")
        click.echo()
        click.echo("Run `linkedout enrich` to start enrichment.")
        click.echo("Run `linkedout enrich --limit 1000` to enrich a subset.")
        return

    # 3. Validate API key (fail early)
    try:
        get_platform_apify_key()
    except ValueError:
        click.echo("Error: No Apify API key configured.")
        click.echo()
        click.echo("Set APIFY_API_KEY for a single key, or")
        click.echo("APIFY_API_KEYS=key1,key2,key3 for round-robin.")
        click.echo()
        click.echo("Configure in secrets.yaml, .env, or environment variables.")
        raise SystemExit(1)

    # 4. Set up factories (needed for both recovery and main pipeline)
    effective_skip_embeddings = skip_embeddings or cfg.enrichment.skip_embeddings

    embedding_provider = None
    if not effective_skip_embeddings:
        from utilities.llm_manager.embedding_factory import get_embedding_provider
        try:
            embedding_provider = get_embedding_provider()
        except Exception as e:
            click.echo(f"Warning: Could not initialize embedding provider: {e}")
            click.echo("Continuing without embeddings. Run `linkedout embed` later.")

    def db_session_factory():
        return db_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID)

    def post_enrichment_factory(session):
        return PostEnrichmentService(session, embedding_provider=embedding_provider)

    # 5. Recover incomplete batches from prior runs (no Apify cost)
    recovery = recover_incomplete_batches(
        data_dir=data_dir,
        db_session_factory=db_session_factory,
        post_enrichment_factory=post_enrichment_factory,
        skip_embeddings=effective_skip_embeddings,
    )
    if recovery.recovered > 0:
        click.echo(f"Recovered {recovery.recovered:,} profiles from prior incomplete run")
        # Re-query unenriched profiles (some are now enriched)
        with db_manager.get_session(DbSessionType.READ, app_user_id=SYSTEM_USER_ID) as session:
            rows = session.execute(text(
                "SELECT id, linkedin_url FROM crawled_profile "
                "WHERE has_enriched_data = false "
                "AND linkedin_url LIKE '%linkedin.com/%'"
            )).fetchall()
        profiles = [(r[0], r[1]) for r in rows]
        if limit is not None:
            profiles = profiles[:limit]
        total = len(profiles)
        if total == 0:
            click.echo("All profiles are now enriched after recovery. Nothing more to do.")
            return
    if recovery.failed > 0:
        click.echo(f"  {recovery.failed:,} profiles in failed Apify batches (will retry)")

    # 6. Cost estimate
    est_cost = total * cost_per
    click.echo(f"Enriching {total:,} profiles (~${est_cost:.2f})")

    # 7. Progress callback
    def on_progress(enriched, failed, total_profiles, batch_idx):
        elapsed = time.time() - start_time
        done = enriched + failed
        pct = done / total_profiles * 100 if total_profiles else 0
        cost_so_far = enriched * cost_per
        if done < total_profiles and elapsed > 0:
            rate = elapsed / done
            remaining = rate * (total_profiles - done)
            remaining_str = f"~{_format_duration(remaining)} remaining"
        else:
            remaining_str = "done"
        click.echo(
            f"  Batch {batch_idx}: {done}/{total_profiles} "
            f"({pct:.1f}%) | ${cost_so_far:.2f} | {remaining_str}"
        )

    # 8. Run the pipeline (new batches only — recovery already handled above)
    from linkedout.enrichment_pipeline.bulk_enrichment import enrich_profiles

    result = enrich_profiles(
        profiles=profiles,
        db_session_factory=db_session_factory,
        post_enrichment_factory=post_enrichment_factory,
        embedding_provider=embedding_provider,
        skip_embeddings=effective_skip_embeddings,
        on_progress=on_progress,
    )

    # 9. Summary
    elapsed = time.time() - start_time
    cost_total = result.enriched * cost_per

    if result.stopped_reason == "all_keys_exhausted":
        click.echo("\nStopped: all API keys exhausted.")
    elif result.stopped_reason == "interrupted":
        click.echo("\nInterrupted by user.")

    click.echo(
        f"\nEnrichment complete: {result.enriched:,} enriched, "
        f"{result.failed:,} failed ({result.batches_completed}/{result.batches_total} batches) "
        f"(${cost_total:.2f}, {_format_duration(elapsed)})"
    )

    # 10. Metrics + report
    record_metric(
        "profiles_enriched", result.enriched,
        duration_ms=elapsed * 1000, failed=result.failed,
    )

    report = OperationReport(
        operation="enrich",
        duration_ms=elapsed * 1000,
        counts=OperationCounts(
            total=total,
            succeeded=result.enriched,
            skipped=0,
            failed=result.failed,
        ),
        next_steps=_build_next_steps(effective_skip_embeddings),
    )
    report_path = report.save()

    # 11. Next steps
    click.echo("\nNext steps:")
    for step in _build_next_steps(effective_skip_embeddings):
        click.echo(f"  -> {step}")

    try:
        display = '~/' + str(report_path.relative_to(Path.home()))
    except ValueError:
        display = str(report_path)
    click.echo(f"\nReport saved: {display}")
