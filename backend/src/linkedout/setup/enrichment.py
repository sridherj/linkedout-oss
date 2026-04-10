# SPDX-License-Identifier: Apache-2.0
"""Apify profile enrichment orchestration for LinkedOut setup.

Enriches unenriched profiles (``has_enriched_data=False``) using the
existing Apify enrichment pipeline. Runs after CSV/contacts import and
before seed data, so downstream steps (embeddings, affinity) benefit
from the richer profile data.

All operations are idempotent — already-enriched profiles are skipped,
and partial runs can be resumed safely.
"""
from __future__ import annotations

import time
from pathlib import Path

from sqlalchemy import func, select

from linkedout.setup.logging_integration import get_setup_logger
from shared.utilities.operation_report import (
    OperationCounts,
    OperationFailure,
    OperationReport,
)

# Budget cap: max profiles to enrich in a single setup run.
# At ~$0.004/profile this keeps the cost under $0.10.
_DEFAULT_MAX_PROFILES = 20

_COST_PER_PROFILE = 0.004  # USD, mirrors EnrichmentConfig default


def _has_apify_key() -> bool:
    """Check whether an Apify API key is configured.

    Checks both the config system (secrets.yaml / env) and raw
    environment variables as a fallback.
    """
    import os

    # Check env vars directly first (avoids config init side effects)
    if os.environ.get("APIFY_API_KEY") or os.environ.get("APIFY_API_KEYS"):
        return True

    try:
        from shared.config import get_config
        cfg = get_config()
        if cfg.get_apify_api_keys():
            return True
        if cfg.apify_api_key:
            return True
    except Exception:
        pass

    return False


def count_unenriched_profiles(db_url: str) -> int:
    """Count profiles with ``has_enriched_data=False`` and a LinkedIn URL.

    Args:
        db_url: Database connection URL.

    Returns:
        Number of profiles eligible for enrichment.
    """
    from sqlalchemy import create_engine

    from linkedout.crawled_profile.entities.crawled_profile_entity import (
        CrawledProfileEntity,
    )

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            result = conn.execute(
                select(func.count())
                .select_from(CrawledProfileEntity)
                .where(
                    CrawledProfileEntity.has_enriched_data == False,  # noqa: E712
                    CrawledProfileEntity.linkedin_url.isnot(None),
                )
            )
            return result.scalar() or 0
    finally:
        engine.dispose()


def run_enrichment(db_url: str, max_profiles: int = _DEFAULT_MAX_PROFILES) -> OperationReport:
    """Enrich unenriched profiles using the Apify pipeline.

    Loads profiles from the database, calls Apify synchronously for
    each one (with retry), and delegates post-processing to
    ``PostEnrichmentService``.

    Args:
        db_url: Database connection URL.
        max_profiles: Maximum number of profiles to enrich.

    Returns:
        OperationReport with enriched/failed/skipped counts.
    """
    log = get_setup_logger("enrichment")
    start = time.monotonic()

    from dev_tools.db.fixed_data import SYSTEM_BU, SYSTEM_TENANT, SYSTEM_USER_ID
    from linkedout.crawled_profile.entities.crawled_profile_entity import (
        CrawledProfileEntity,
    )
    from linkedout.enrichment_pipeline.apify_client import (
        LinkedOutApifyClient,
        get_platform_apify_key,
    )
    from linkedout.enrichment_pipeline.post_enrichment import PostEnrichmentService
    from shared.infra.db.cli_db import cli_db_manager
    from shared.infra.db.db_session_manager import DbSessionType

    db_manager = cli_db_manager()

    # Load unenriched profiles
    with db_manager.get_session(DbSessionType.READ, app_user_id=SYSTEM_USER_ID) as session:
        profiles = (
            session.execute(
                select(CrawledProfileEntity)
                .where(
                    CrawledProfileEntity.has_enriched_data == False,  # noqa: E712
                    CrawledProfileEntity.linkedin_url.isnot(None),
                )
                .limit(max_profiles)
            )
            .scalars()
            .all()
        )
        # Detach the data we need before session closes
        targets = [
            (p.id, p.linkedin_url)
            for p in profiles
        ]

    total = len(targets)
    if total == 0:
        duration_ms = (time.monotonic() - start) * 1000
        return OperationReport(
            operation="setup-enrichment",
            duration_ms=duration_ms,
            counts=OperationCounts(total=0, succeeded=0),
        )

    enriched = 0
    failed = 0
    failures = []

    for i, (profile_id, linkedin_url) in enumerate(targets, 1):
        print(f"  [{i}/{total}] Enriching {linkedin_url}...", end="", flush=True)

        try:
            api_key = get_platform_apify_key()
            client = LinkedOutApifyClient(api_key)
            result = client.enrich_profile_sync(linkedin_url)

            if not result:
                print(" no data returned")
                failed += 1
                failures.append((linkedin_url, "Apify returned no data"))
                continue

            # Process result in a write session
            with db_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
                from utilities.llm_manager.embedding_factory import get_embedding_provider
                embedding_provider = get_embedding_provider()
                service = PostEnrichmentService(session, embedding_provider)
                # PostEnrichmentService expects an enrichment_event_id.
                # For setup, we create a minimal event inline.
                from linkedout.enrichment_event.entities.enrichment_event_entity import (
                    EnrichmentEventEntity,
                )
                event = EnrichmentEventEntity(
                    tenant_id=SYSTEM_TENANT['id'],
                    bu_id=SYSTEM_BU['id'],
                    app_user_id=SYSTEM_USER_ID,
                    crawled_profile_id=profile_id,
                    event_type="queued",
                    enrichment_mode="platform",
                    cost_estimate_usd=_COST_PER_PROFILE,
                )
                session.add(event)
                session.flush()

                service.process_enrichment_result(result, event.id, linkedin_url)

            enriched += 1
            print(" done")

        except Exception as exc:
            print(f" failed: {exc}")
            log.warning("Enrichment failed for {}: {}", linkedin_url, exc)
            failed += 1
            failures.append((linkedin_url, str(exc)))

    duration_ms = (time.monotonic() - start) * 1000
    cost = round(enriched * _COST_PER_PROFILE, 4)

    log.info(
        "Enrichment complete: {}/{} succeeded, {} failed, cost ~${}, {:.1f}s",
        enriched, total, failed, cost, duration_ms / 1000,
    )

    return OperationReport(
        operation="setup-enrichment",
        duration_ms=duration_ms,
        counts=OperationCounts(total=total, succeeded=enriched, failed=failed),
        failures=[
            OperationFailure(item=url, reason=reason)
            for url, reason in failures
        ],
    )


def setup_enrichment(data_dir: Path, db_url: str) -> OperationReport:  # noqa: ARG001
    """Full enrichment orchestration for the setup flow.

    Steps:
    1. Check for Apify API key — skip gracefully if missing
    2. Count unenriched profiles
    3. Show cost estimate and ask for confirmation
    4. Run enrichment
    5. Report results

    Args:
        data_dir: Root data directory (e.g., ``~/linkedout-data``).
        db_url: Database connection URL.

    Returns:
        OperationReport summarizing what was done.
    """
    start = time.monotonic()

    # Step 1: Check for API key
    if not _has_apify_key():
        print("  No Apify API key found. Skipping enrichment.")
        print()
        print("  To enrich profiles later:")
        print("    1. Get a free API key at https://apify.com/")
        print("    2. Set APIFY_API_KEY in your environment or secrets.yaml")
        print("    3. Run: linkedout setup  (enrichment will run automatically)")
        duration_ms = (time.monotonic() - start) * 1000
        return OperationReport(
            operation="setup-enrichment",
            duration_ms=duration_ms,
            counts=OperationCounts(total=0, skipped=1),
            next_steps=["Set APIFY_API_KEY and re-run setup to enrich profiles"],
        )

    # Step 2: Count unenriched profiles
    count = count_unenriched_profiles(db_url)

    if count == 0:
        print("  All profiles already enriched. Nothing to do.")
        duration_ms = (time.monotonic() - start) * 1000
        return OperationReport(
            operation="setup-enrichment",
            duration_ms=duration_ms,
            counts=OperationCounts(total=0, succeeded=0),
        )

    # Step 3: Show estimate and confirm
    batch_size = min(count, _DEFAULT_MAX_PROFILES)
    cost_estimate = round(batch_size * _COST_PER_PROFILE, 2)
    time_estimate = _estimate_time(batch_size)

    print(f"  Profiles needing enrichment: {count:,}")
    if count > batch_size:
        print(f"  Budget cap: {batch_size} profiles (of {count:,} total)")
    print(f"  Estimated time: {time_estimate}")
    print(f"  Estimated cost: ~${cost_estimate:.2f} (~${_COST_PER_PROFILE}/profile)")
    print()

    try:
        choice = input("  Enrich profiles now? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        choice = ""  # default to yes (enrich if key exists)
    if choice in ("n", "no"):
        print("\n  Skipping enrichment.")
        print("  You can enrich later by re-running: linkedout setup")
        duration_ms = (time.monotonic() - start) * 1000
        return OperationReport(
            operation="setup-enrichment",
            duration_ms=duration_ms,
            counts=OperationCounts(total=0, succeeded=0, skipped=count),
            next_steps=["Re-run `linkedout setup` to enrich profiles"],
        )

    # Step 4: Run enrichment
    print()
    report = run_enrichment(db_url, max_profiles=batch_size)

    # Step 5: Summary
    c = report.counts
    print()
    print(f"  Enrichment complete: {c.succeeded} enriched, {c.failed} failed, {c.skipped} skipped")
    if c.succeeded > 0:
        cost = round(c.succeeded * _COST_PER_PROFILE, 4)
        print(f"  Estimated cost: ~${cost:.4f}")
    if count > batch_size and c.succeeded > 0:
        remaining = count - c.succeeded
        print(f"  {remaining:,} profiles remain unenriched (re-run setup to continue)")

    duration_ms = (time.monotonic() - start) * 1000
    return OperationReport(
        operation="setup-enrichment",
        duration_ms=duration_ms,
        counts=report.counts,
        failures=report.failures,
        next_steps=report.next_steps,
    )


def _estimate_time(count: int) -> str:
    """Return a human-readable time estimate for enriching *count* profiles.

    Each Apify sync call takes ~5-15 seconds.
    """
    low_seconds = count * 5
    high_seconds = count * 15

    if high_seconds < 60:
        return f"~{low_seconds}-{high_seconds} seconds"
    low_min = max(1, low_seconds // 60)
    high_min = (high_seconds + 59) // 60
    return f"~{low_min}-{high_min} minutes"
