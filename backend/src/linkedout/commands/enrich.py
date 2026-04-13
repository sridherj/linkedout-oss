# SPDX-License-Identifier: Apache-2.0
"""``linkedout enrich`` — enrich unenriched LinkedIn profiles via Apify.

Queries ``crawled_profile`` rows that lack enrichment data, calls the Apify
LinkedIn scraper for each, and processes the results into relational data.
Supports ``--dry-run`` for cost estimation and ``--limit`` for partial runs.
"""
import os
import signal
import time
from pathlib import Path

import click
from sqlalchemy import text

from dev_tools.db.fixed_data import SYSTEM_BU, SYSTEM_TENANT, SYSTEM_USER_ID
from linkedout.cli_helpers import cli_logged
from linkedout.enrichment_event.entities.enrichment_event_entity import EnrichmentEventEntity
from linkedout.enrichment_pipeline.apify_client import (
    LinkedOutApifyClient,
    get_platform_apify_key,
)
from linkedout.enrichment_pipeline.post_enrichment import PostEnrichmentService
from shared.config import get_config
from shared.infra.db.cli_db import cli_db_manager
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger
from shared.utilities.metrics import record_metric
from shared.utilities.operation_report import OperationCounts, OperationReport

logger = get_logger(__name__, component="cli", operation="enrich")

APP_USER_ID = SYSTEM_USER_ID
TENANT_ID = SYSTEM_TENANT['id']
BU_ID = SYSTEM_BU['id']

PROGRESS_INTERVAL = 25


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


def _get_reports_dir() -> Path:
    """Return the reports directory path."""
    reports_dir = os.environ.get(
        'LINKEDOUT_REPORTS_DIR',
        str(Path.home() / 'linkedout-data' / 'reports'),
    )
    return Path(reports_dir)


@click.command('enrich')
@click.option('--limit', type=int, default=None,
              help='Max profiles to enrich (default: all unenriched)')
@click.option('--dry-run', is_flag=True,
              help='Count unenriched profiles, estimate cost, exit without calling Apify')
@cli_logged("enrich")
def enrich_command(limit: int | None, dry_run: bool):
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

    # 2. Dry-run
    if dry_run:
        est_cost = total_unenriched * cost_per
        click.echo(f"Dry run: {total_unenriched:,} unenriched profiles found")
        click.echo(f"Estimated cost: ${est_cost:.2f} (~${cost_per * 1000:.2f} per 1,000 profiles)")
        click.echo()
        click.echo("Run `linkedout enrich` to start enrichment.")
        click.echo("Run `linkedout enrich --limit 1000` to enrich a subset.")
        return

    # 3. Get Apify key (fail early with clean message)
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

    # 4. Print cost estimate
    est_cost = total * cost_per
    click.echo(f"Estimated cost: ~${est_cost:.2f} (~${cost_per * 1000:.2f} per 1,000 profiles)")
    click.echo()

    # 5. Enrichment loop with Ctrl+C safety
    enriched = 0
    failed = 0
    cost_so_far = 0.0
    interrupted = False

    def _on_interrupt(signum, frame):
        nonlocal interrupted
        interrupted = True

    old_handler = signal.signal(signal.SIGINT, _on_interrupt)

    click.echo("Enriching profiles...")
    try:
        for i, (profile_id, linkedin_url) in enumerate(profiles):
            if interrupted:
                break

            try:
                api_key = get_platform_apify_key()
                client = LinkedOutApifyClient(api_key)
                apify_data = client.enrich_profile_sync(linkedin_url)

                if apify_data is not None:
                    with db_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
                        event = EnrichmentEventEntity(
                            tenant_id=TENANT_ID,
                            bu_id=BU_ID,
                            app_user_id=APP_USER_ID,
                            crawled_profile_id=profile_id,
                            event_type='queued',
                            enrichment_mode='platform',
                            crawler_name='apify',
                            cost_estimate_usd=0.0,
                        )
                        session.add(event)
                        session.flush()

                        service = PostEnrichmentService(session, embedding_provider=None)
                        service.process_enrichment_result(apify_data, event.id, linkedin_url)

                    enriched += 1
                    cost_so_far += cost_per
                else:
                    failed += 1
                    logger.warning(f"Apify returned None for {linkedin_url}")

            except Exception as e:
                failed += 1
                logger.error(f"Enrichment failed for {linkedin_url}: {e}")

            # Progress reporting every PROGRESS_INTERVAL profiles
            done = i + 1
            if done % PROGRESS_INTERVAL == 0 or done == total:
                elapsed = time.time() - start_time
                pct = done / total * 100
                if done < total and elapsed > 0:
                    rate = elapsed / done
                    remaining = rate * (total - done)
                    remaining_str = f"~{_format_duration(remaining)} remaining"
                else:
                    remaining_str = "done"
                click.echo(
                    f"  [{done:>{len(str(total))}}/{total}] "
                    f"{pct:5.1f}% | ${cost_so_far:.2f} spent | "
                    f"{elapsed:.0f}s elapsed | {remaining_str}"
                )
    finally:
        signal.signal(signal.SIGINT, old_handler)

    elapsed = time.time() - start_time

    if interrupted:
        click.echo(
            f"\nInterrupted. {enriched:,}/{total:,} profiles enriched "
            f"(${cost_so_far:.2f})."
        )
        return

    # 6. Record metric
    record_metric(
        "profiles_enriched", enriched,
        duration_ms=elapsed * 1000, failed=failed,
    )

    # 7. Build and save operation report
    report = OperationReport(
        operation="enrich",
        duration_ms=elapsed * 1000,
        counts=OperationCounts(
            total=total,
            succeeded=enriched,
            skipped=0,
            failed=failed,
        ),
        next_steps=[
            "Run `linkedout embed` to generate embeddings for semantic search",
            "Run `linkedout compute-affinity` to calculate affinity scores",
        ],
    )
    report_path = report.save()

    # 8. Final summary
    click.echo(
        f"\nEnrichment complete: {enriched:,} profiles enriched "
        f"(${cost_so_far:.2f}, {_format_duration(elapsed)})"
    )
    click.echo()
    click.echo("Next steps:")
    click.echo("  -> Run `linkedout embed` to generate embeddings for semantic search")
    click.echo("  -> Run `linkedout compute-affinity` to calculate affinity scores")

    try:
        display = '~/' + str(report_path.relative_to(Path.home()))
    except ValueError:
        display = str(report_path)
    click.echo(f"\nReport saved: {display}")

    # Suppress unused var warning
    _ = report
