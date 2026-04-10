# SPDX-License-Identifier: Apache-2.0
"""``linkedout embed`` — generate vector embeddings for profile search.

Queries enriched ``crawled_profile`` rows, generates embedding vectors via
the configured provider (OpenAI or local nomic), and writes them to the
correct pgvector column.  Resumable, idempotent, supports ``--dry-run``
and ``--force``.
"""
import json
import os
import signal
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import click
from sqlalchemy import text

from linkedout.cli_helpers import cli_logged
from dev_tools.db.fixed_data import SYSTEM_USER_ID
from shared.config import get_config
from shared.infra.db.cli_db import cli_db_manager
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger
from shared.utilities.metrics import record_metric
from shared.utilities.operation_report import (
    OperationCounts,
    OperationReport,
)
from utilities.embedding_progress import EmbeddingProgress, get_progress_path
from utilities.llm_manager.embedding_factory import get_embedding_column_name, get_embedding_provider
from utilities.llm_manager.embedding_provider import build_embedding_text

logger = get_logger(__name__, component="cli", operation="embed")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def fetch_profiles_needing_embeddings(
    session,
    column_name: str,
    *,
    after_id: str | None = None,
) -> list[dict]:
    """Fetch enriched profiles that lack embeddings in the target column."""
    where_clauses = [
        "has_enriched_data = TRUE",
        f"{column_name} IS NULL",
    ]
    params: dict = {}
    if after_id:
        where_clauses.append("id > :after_id")
        params["after_id"] = after_id

    where = " AND ".join(where_clauses)

    profiles_rows = session.execute(text(
        f"SELECT id, full_name, headline, about, current_company_name, current_position "
        f"FROM crawled_profile "
        f"WHERE {where} "
        f"ORDER BY id"
    ), params).fetchall()

    if not profiles_rows:
        return []

    profile_ids = [r[0] for r in profiles_rows]

    cfg = get_config()
    chunk_size = cfg.embedding.chunk_size
    exp_by_profile: dict[str, list[dict]] = {}

    for i in range(0, len(profile_ids), chunk_size):
        chunk = profile_ids[i:i + chunk_size]
        placeholders = ','.join(f':id_{j}' for j in range(len(chunk)))
        id_params = {f'id_{j}': pid for j, pid in enumerate(chunk)}
        exp_rows = session.execute(text(
            f"SELECT crawled_profile_id, company_name, position "
            f"FROM experience "
            f"WHERE crawled_profile_id IN ({placeholders}) "
            f"ORDER BY crawled_profile_id, start_date DESC NULLS LAST"
        ), id_params).fetchall()

        for row in exp_rows:
            exp_by_profile.setdefault(row[0], []).append({
                'company_name': row[1],
                'title': row[2],
            })

    profiles = []
    for row in profiles_rows:
        profiles.append({
            'id': row[0],
            'full_name': row[1],
            'headline': row[2],
            'about': row[3],
            'current_company_name': row[4],
            'current_position': row[5],
            'experiences': exp_by_profile.get(row[0], []),
        })

    return profiles


def build_batch_items(profiles: list[dict]) -> list[dict]:
    """Build batch items with ``custom_id`` and ``text`` for each profile."""
    items = []
    for profile in profiles:
        text_val = build_embedding_text(profile)
        if not text_val or not text_val.strip():
            continue
        items.append({
            'custom_id': profile['id'],
            'text': text_val,
        })
    return items


def update_embeddings(
    results: dict[str, list[float]],
    column_name: str,
    model_name: str,
    dimension: int,
    batch_size: int = 500,
) -> int:
    """Write embedding vectors back to ``crawled_profile``. Returns count updated."""
    db_manager = cli_db_manager()
    updated = 0
    items = list(results.items())
    total = len(items)

    for i in range(0, total, batch_size):
        chunk = items[i:i + batch_size]
        with db_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
            for profile_id, embedding in chunk:
                embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
                session.execute(text(
                    f"UPDATE crawled_profile "
                    f"SET {column_name} = CAST(:emb AS vector), "
                    f"    embedding_model = :model, "
                    f"    embedding_dim = :dim, "
                    f"    embedding_updated_at = NOW() "
                    f"WHERE id = :pid"
                ), {
                    'emb': embedding_str,
                    'model': model_name,
                    'dim': dimension,
                    'pid': profile_id,
                })
                updated += 1

    return updated


def populate_search_vectors() -> int:
    """Populate ``search_vector`` (tsvector) for all enriched profiles."""
    db_manager = cli_db_manager()
    with db_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
        result = session.execute(text(
            "UPDATE crawled_profile SET search_vector = "
            "to_tsvector('english', "
            "  coalesce(full_name,'') || ' ' || "
            "  coalesce(headline,'') || ' ' || "
            "  coalesce(about,'') || ' ' || "
            "  coalesce(current_company_name,'') || ' ' || "
            "  coalesce(current_position,'')) "
            "WHERE has_enriched_data = TRUE"
        ))
        return result.rowcount


def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs:.0f}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


def _resolve_provider_name(provider) -> str:
    """Derive the provider key from a provider instance."""
    if "nomic" in provider.model_name().lower():
        return "local"
    return "openai"


def _get_reports_dir() -> Path:
    """Return the reports directory path."""
    reports_dir = os.environ.get(
        'LINKEDOUT_REPORTS_DIR',
        str(Path.home() / 'linkedout-data' / 'reports'),
    )
    return Path(reports_dir)


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------

@click.command('embed')
@click.option('--provider', 'provider_name', type=click.Choice(['openai', 'local']),
              default=None, help='Embedding provider (default: from config)')
@click.option('--dry-run', is_flag=True, help='Report what would be embedded, do not run')
@click.option('--resume/--no-resume', default=True, help='Resume from last checkpoint (default: true)')
@click.option('--force', is_flag=True, help='Re-embed all profiles, even those with current embeddings')
@click.option('--batch', 'batch_api', is_flag=True,
              help='Use OpenAI Batch API (OpenAI provider only, 50%% cheaper but slower)')
@cli_logged("embed")
def embed_command(provider_name: str | None, dry_run: bool, resume: bool, force: bool, batch_api: bool):
    """Generate embeddings for profile search."""
    db_manager = cli_db_manager()
    start_time = time.time()

    # 1. Resolve provider
    embedding_provider = get_embedding_provider(provider=provider_name)
    column_name = get_embedding_column_name(embedding_provider)
    prov_key = _resolve_provider_name(embedding_provider)
    model = embedding_provider.model_name()
    dim = embedding_provider.dimension()

    if batch_api:
        from utilities.llm_manager.openai_embedding_provider import OpenAIEmbeddingProvider
        if not isinstance(embedding_provider, OpenAIEmbeddingProvider):
            raise click.UsageError(
                '--batch is only supported with the OpenAI provider. '
                'Use --provider openai --batch.'
            )

    # 2. Check progress file for resumability
    progress_path = get_progress_path()
    progress: EmbeddingProgress | None = None if force else EmbeddingProgress.load(progress_path)

    if progress and progress.status != "completed" and progress.provider != prov_key:
        click.echo(
            f"Warning: Previous run used provider '{progress.provider}' "
            f"but current provider is '{prov_key}'. Starting fresh."
        )
        progress_path.unlink(missing_ok=True)
        progress = None

    if progress and progress.status == "completed" and not force:
        click.echo(
            f"All profiles already embedded with {progress.model}. "
            f"Use --force to re-embed."
        )
        return

    # 3. If --force, clear target column
    if force:
        progress_path.unlink(missing_ok=True)
        progress = None
        with db_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
            result = session.execute(text(
                f"UPDATE crawled_profile SET {column_name} = NULL "
                f"WHERE {column_name} IS NOT NULL"
            ))
            if result.rowcount > 0:
                click.echo(f"Cleared {result.rowcount:,} existing embeddings in {column_name}")

    # 4. Fetch profiles needing embeddings
    resume_id = progress.last_processed_id if progress else None

    with db_manager.get_session(DbSessionType.READ, app_user_id=SYSTEM_USER_ID) as session:
        profiles = fetch_profiles_needing_embeddings(session, column_name, after_id=resume_id)

    if not profiles:
        if resume_id:
            click.echo("Resume complete -- no remaining profiles need embedding.")
        else:
            click.echo("No profiles need embedding.")
        return

    total_count = len(profiles)

    # 5. Dry-run
    if dry_run:
        click.echo("\n--- DRY RUN ---")
        click.echo(f"  Profiles needing embedding: {total_count:,}")
        click.echo(f"  Provider: {model} ({dim}d, {prov_key})")
        click.echo(f"  Target column: {column_name}")
        click.echo(f"  Estimated time: {embedding_provider.estimate_time(total_count)}")
        cost = embedding_provider.estimate_cost(total_count)
        if cost:
            click.echo(f"  Estimated cost: {cost}")
        if resume_id:
            click.echo(f"  Resuming from: {resume_id}")
        return

    # 6. Initialize or continue progress
    if not progress:
        progress = EmbeddingProgress(
            provider=prov_key,
            model=model,
            dimension=dim,
            total_profiles=total_count,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

    # 7. Print header
    click.echo(f"Embedding {total_count:,} profiles with {model} ({dim}d, {prov_key})...")
    click.echo(f"Estimated time: {embedding_provider.estimate_time(total_count)}")
    cost = embedding_provider.estimate_cost(total_count)
    if cost:
        click.echo(f"Estimated cost: {cost}")

    # 8. Build batch items
    items = build_batch_items(profiles)
    if not items:
        click.echo("No valid items to embed (all profiles had empty text).")
        return
    skipped_empty = total_count - len(items)

    if batch_api:
        embedded, failed = _run_batch_api(
            embedding_provider, items, column_name, model, dim, progress, progress_path,
        )
    else:
        embedded, failed = _run_realtime(
            embedding_provider, items, column_name, model, dim, progress, progress_path,
        )

    # 9. Populate search vectors
    click.echo("Populating search vectors...")
    populate_search_vectors()

    # 10. Mark complete
    progress.mark_completed()
    progress.save(progress_path)

    elapsed = time.time() - start_time

    # 11. Record metric
    record_metric(
        "embedding_generated", embedded,
        model=model, duration_ms=elapsed * 1000,
        mode="batch_api" if batch_api else "realtime",
        failed=failed,
    )

    # 12. Build and save operation report
    report = OperationReport(
        operation="embed",
        duration_ms=elapsed * 1000,
        counts=OperationCounts(
            total=total_count,
            succeeded=embedded,
            skipped=skipped_empty,
            failed=failed,
        ),
        next_steps=["Run `linkedout compute-affinity` to update affinity scores"],
    )

    reports_dir = _get_reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report_path = reports_dir / f"embed-{prov_key}-{ts_str}.json"
    report_data = {
        "operation": "embed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round(elapsed * 1000),
        "provider": model,
        "dimension": dim,
        "counts": {
            "total": total_count,
            "embedded": embedded,
            "skipped": skipped_empty,
            "failed": failed,
        },
        "coverage_gaps": [],
        "failures": [{"id": fid} for fid in progress.failed_ids[:20]],
        "next_steps": ["Run `linkedout compute-affinity` to update affinity scores"],
    }
    report_path.write_text(json.dumps(report_data, indent=2))

    # 13. Print operation result pattern
    click.echo("\nResults:")
    click.echo(f"  Embedded:   {embedded:,} profiles")
    click.echo(f"  Skipped:    {skipped_empty:,} (empty text)")
    click.echo(f"  Failed:     {failed:,}")
    click.echo(f"  Provider:   {model} ({dim}d)")
    click.echo(f"  Duration:   {_format_duration(elapsed)}")

    click.echo("\nNext steps:")
    click.echo("  -> Run `linkedout compute-affinity` to update affinity scores")

    try:
        display = '~/' + str(report_path.relative_to(Path.home()))
    except ValueError:
        display = str(report_path)
    click.echo(f"\nReport saved: {display}")

    # Suppress unused var warning — report object used for its side effects
    _ = report


# ---------------------------------------------------------------------------
# Real-time embedding
# ---------------------------------------------------------------------------

def _run_realtime(
    provider,
    items: list[dict],
    column_name: str,
    model_name: str,
    dimension: int,
    progress: EmbeddingProgress,
    progress_path: Path,
) -> tuple[int, int]:
    """Embed items via real-time API with progress bar and Ctrl+C safety."""
    cfg = get_config()
    chunk_size = cfg.embedding.chunk_size
    total = len(items)
    embedded = 0
    failed = 0
    interrupted = False

    def _on_interrupt(signum, frame):
        nonlocal interrupted
        interrupted = True

    old_handler = signal.signal(signal.SIGINT, _on_interrupt)

    try:
        with click.progressbar(length=total, label='Embedding') as bar:
            for i in range(0, total, chunk_size):
                if interrupted:
                    break

                chunk = items[i:i + chunk_size]
                texts = [item['text'] for item in chunk]

                try:
                    vectors = provider.embed(texts)
                except Exception as e:
                    logger.error("Embedding batch failed", error=str(e), batch_start=i)
                    failed += len(chunk)
                    progress.failed_ids.extend(item['custom_id'] for item in chunk)
                    progress.mark_failed(str(e))
                    progress.save(progress_path)
                    raise click.ClickException(
                        f"Embedding failed: {e}\n"
                        f"Progress saved. Run `linkedout embed` to resume."
                    )

                results = {item['custom_id']: vec for item, vec in zip(chunk, vectors)}
                update_embeddings(results, column_name, model_name, dimension)
                embedded += len(chunk)

                progress.mark_batch_complete(chunk[-1]['custom_id'], len(chunk))
                progress.save(progress_path)
                bar.update(len(chunk))
    finally:
        signal.signal(signal.SIGINT, old_handler)

    if interrupted:
        click.echo(f"\nInterrupted. Progress saved ({embedded:,}/{total:,} embedded).")
        click.echo("Run `linkedout embed` to resume.")
        progress.save(progress_path)

    return embedded, failed


# ---------------------------------------------------------------------------
# Batch API embedding (OpenAI-specific)
# ---------------------------------------------------------------------------

def _run_batch_api(
    provider,
    items: list[dict],
    column_name: str,
    model_name: str,
    dimension: int,
    progress: EmbeddingProgress,
    progress_path: Path,
) -> tuple[int, int]:
    """Embed items via OpenAI Batch API."""
    cfg = get_config()
    poll_interval = cfg.embedding.batch_poll_interval_seconds
    timeout = cfg.embedding.batch_timeout_seconds

    click.echo(f"Submitting {len(items):,} items to OpenAI Batch API...")
    click.echo(f"  (poll_interval={poll_interval}s, timeout={timeout}s)")

    fd, tmp_path = tempfile.mkstemp(suffix='.jsonl', prefix='embeddings_batch_')
    os.close(fd)

    try:
        results = provider.embed_batch_async(
            items, tmp_path,
            poll_interval=poll_interval,
            timeout=timeout,
            progress_callback=lambda msg: click.echo(f"  -> {msg}"),
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    click.echo(f"  -> {len(results):,} embeddings received")

    failed = len(items) - len(results)
    if failed > 0:
        click.echo(f"  -> {failed} items failed")
        submitted_ids = {item['custom_id'] for item in items}
        missing = submitted_ids - set(results.keys())
        progress.failed_ids.extend(list(missing)[:100])

    click.echo("Updating embeddings in database...")
    embedded = update_embeddings(results, column_name, model_name, dimension)
    click.echo(f"  -> {embedded:,} profiles updated")

    if items:
        progress.mark_batch_complete(items[-1]['custom_id'], embedded)
        progress.save(progress_path)

    return embedded, failed
