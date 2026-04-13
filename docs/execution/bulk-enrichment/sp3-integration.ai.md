# SP3: Integration

**Depends on:** SP1 (settings, archive batch), SP2 (bulk_enrichment.py)
**Produces:** `process_batch()` in post_enrichment.py, rewritten `enrich.py` CLI command
**Estimated scope:** ~200 lines changed across 2 files

## Overview

Wire the core pipeline (SP2) into the existing system:

1. Add `process_batch()` to `PostEnrichmentService` — batch embedding + batch JSONL archive
2. Rewrite `commands/enrich.py` to use the bulk pipeline instead of serial sync calls

---

## Change 1: `process_batch()` in post_enrichment.py

**File:** `backend/src/linkedout/enrichment_pipeline/post_enrichment.py`
**Class:** `PostEnrichmentService`

### What to Add

Add a new method `process_batch()` that processes N Apify results with batch embedding and batch archiving, while delegating per-profile DB writes to the existing `process_enrichment_result()`.

```python
def process_batch(
    self,
    results: list[tuple[str, str, dict]],  # list of (profile_id, linkedin_url, apify_data)
    enrichment_event_ids: dict[str, str],   # linkedin_url -> event_id
    skip_embeddings: bool = False,
    source: str = 'bulk_enrichment',
) -> tuple[int, int]:
    """Process a batch of Apify results with batched embedding and archiving.

    Flow:
    1. Per-profile DB writes via process_enrichment_result() (embedding_provider=None)
    2. Batch embedding (unless skip_embeddings)
    3. Batch JSONL archive

    Returns:
        (enriched_count, failed_count)
    """
```

### Implementation Details

#### Step 1: Per-Profile DB Writes

Loop through results, calling `process_enrichment_result()` for each. During this phase, `self._embedding_provider` should be temporarily set to `None` so that `ProfileEnrichmentService.enrich()` skips per-profile embedding. Embedding is deferred to step 2 (batch).

```python
# Save original embedding provider, temporarily disable for per-profile processing
original_provider = self._embedding_provider
self._embedding_provider = None

enriched_profiles = []  # (profile_id, profile_dict, request) tuples for batch embedding
enriched = 0
failed = 0

for profile_id, linkedin_url, apify_data in results:
    try:
        event_id = enrichment_event_ids.get(linkedin_url)
        self.process_enrichment_result(apify_data, event_id, linkedin_url, source=source)
        enriched += 1
        # Collect data needed for batch embedding
        enriched_profiles.append((profile_id, linkedin_url))
    except Exception as e:
        failed += 1
        logger.error(f"Failed to process {linkedin_url}: {e}")

# Restore embedding provider
self._embedding_provider = original_provider
```

#### Step 2: Batch Embedding

After all DB writes succeed, generate embeddings in one batch call:

```python
if not skip_embeddings and self._embedding_provider and enriched_profiles:
    try:
        # Re-query profiles to get updated data for embedding text
        from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
        from utilities.llm_manager.embedding_provider import build_embedding_text
        from utilities.llm_manager.embedding_factory import get_embedding_column_name
        
        profile_entities = []
        texts = []
        for profile_id, linkedin_url in enriched_profiles:
            profile = self._session.execute(
                select(CrawledProfileEntity).where(CrawledProfileEntity.id == profile_id)
            ).scalar_one_or_none()
            if profile:
                # Build embedding text from profile data
                exp_dicts = []
                for exp in profile.experiences:
                    exp_dicts.append({
                        'company_name': exp.company_name or '',
                        'title': exp.position or '',
                    })
                profile_dict = {
                    'full_name': profile.full_name,
                    'headline': profile.headline,
                    'about': profile.about,
                    'experiences': exp_dicts,
                }
                text = build_embedding_text(profile_dict)
                if text.strip():
                    profile_entities.append(profile)
                    texts.append(text)
        
        if texts:
            # ONE batch API call instead of N individual calls
            vectors = self._embedding_provider.embed(texts)
            column_name = get_embedding_column_name(self._embedding_provider)
            for profile, vector in zip(profile_entities, vectors):
                setattr(profile, column_name, vector)
                profile.embedding_model = self._embedding_provider.model_name()
                profile.embedding_dim = self._embedding_provider.dimension()
                profile.embedding_updated_at = datetime.now(timezone.utc)
            self._session.flush()
    except Exception as e:
        # Embedding failure does NOT lose DB writes (they're already committed)
        logger.error(f"Batch embedding failed: {e}")
        # Log failed embeddings
        for profile_id, _ in enriched_profiles:
            self._log_failed_embedding_entry(profile_id, str(e))
```

Note: `_log_failed_embedding_entry()` writes to the same JSONL file that `ProfileEnrichmentService._log_failed_embedding()` uses. Either reuse that method or add a similar one here.

#### Step 3: Batch JSONL Archive

```python
from shared.utils.apify_archive import append_apify_archive_batch

entries = [
    {'linkedin_url': linkedin_url, 'apify_data': apify_data}
    for _, linkedin_url, apify_data in results
]
append_apify_archive_batch(entries, source=source)
```

Wait — looking at the existing code, `process_enrichment_result()` already calls `append_apify_archive()` per profile (line 74 of post_enrichment.py). For `process_batch()`, we have two options:

**Option A (recommended):** Skip the per-profile archive in `process_enrichment_result()` when called from `process_batch()`, and do the batch archive at the end. This avoids double-archiving.

**Option B:** Let per-profile archiving happen inside `process_enrichment_result()` as-is, and don't add batch archiving. This is simpler but less efficient.

**Go with Option A:** Add a `skip_archive: bool = False` parameter to `process_enrichment_result()`. When `process_batch()` calls it, pass `skip_archive=True`, then do the batch archive at the end.

```python
def process_enrichment_result(
    self,
    apify_data: dict,
    enrichment_event_id: str,
    linkedin_url: str,
    source: str = 'enrichment',
    skip_archive: bool = False,  # NEW: skip per-profile archive when batch will handle it
) -> None:
    # 0. Archive raw Apify response before any DB work
    if not skip_archive:
        append_apify_archive(linkedin_url, apify_data, source=source)
    # ... rest unchanged
```

### Important Notes

- `process_enrichment_result()` signature gets one new optional kwarg (`skip_archive`). All existing callers are unaffected (default `False`).
- The HTTP controller (extension flow) continues to call `process_enrichment_result()` directly with default `skip_archive=False` — no change.
- `process_batch()` is a new method — no existing code calls it.

---

## Change 2: Rewrite `commands/enrich.py`

**File:** `backend/src/linkedout/commands/enrich.py`

### What Changes

Replace the serial sync enrichment loop with a call to `bulk_enrichment.enrich_profiles()`. Keep `--dry-run`, `--limit`, progress reporting. Add `--skip-embeddings`. Auto-resume from state file.

### New CLI Signature

```python
@click.command('enrich')
@click.option('--limit', type=int, default=None,
              help='Max profiles to enrich (default: all unenriched)')
@click.option('--dry-run', is_flag=True,
              help='Count unenriched profiles, estimate cost, exit without calling Apify')
@click.option('--skip-embeddings', is_flag=True,
              help='Skip embedding generation (can be done later with `linkedout embed`)')
@cli_logged("enrich")
def enrich_command(limit: int | None, dry_run: bool, skip_embeddings: bool):
```

### Implementation Outline

```python
def enrich_command(limit, dry_run, skip_embeddings):
    db_manager = cli_db_manager()
    cfg = get_config()
    cost_per = cfg.enrichment.cost_per_profile_usd
    start_time = time.time()

    # 1. Query unenriched profiles (same SQL as before)
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

    if limit is not None:
        profiles = profiles[:limit]
    total = len(profiles)

    # 2. Dry-run (same as before)
    if dry_run:
        est_cost = total_unenriched * cost_per
        click.echo(f"Dry run: {total_unenriched:,} unenriched profiles found")
        click.echo(f"Estimated cost: ${est_cost:.2f} (~${cost_per * 1000:.2f} per 1,000 profiles)")
        click.echo()
        click.echo("Run `linkedout enrich` to start enrichment.")
        return

    # 3. Validate API key (fail early)
    try:
        get_platform_apify_key()
    except ValueError:
        click.echo("Error: No Apify API key configured.")
        raise SystemExit(1)

    # 4. Cost estimate
    est_cost = total * cost_per
    click.echo(f"Enriching {total:,} profiles (~${est_cost:.2f})")

    # 5. Set up embedding provider (unless --skip-embeddings)
    embedding_provider = None
    if not skip_embeddings and not cfg.enrichment.skip_embeddings:
        from utilities.llm_manager.embedding_factory import get_embedding_provider
        try:
            embedding_provider = get_embedding_provider()
        except Exception as e:
            click.echo(f"Warning: Could not initialize embedding provider: {e}")
            click.echo("Continuing without embeddings. Run `linkedout embed` later.")

    # 6. Define session factory + post-enrichment factory for the pipeline
    def db_session_factory():
        return db_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID)

    def post_enrichment_factory(session):
        return PostEnrichmentService(session, embedding_provider=embedding_provider)

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

    # 8. Run the pipeline
    from linkedout.enrichment_pipeline.bulk_enrichment import enrich_profiles

    result = enrich_profiles(
        profiles=profiles,
        db_session_factory=db_session_factory,
        post_enrichment_factory=post_enrichment_factory,
        embedding_provider=embedding_provider,
        skip_embeddings=skip_embeddings or cfg.enrichment.skip_embeddings,
        on_progress=on_progress,
    )

    # 9. Summary
    elapsed = time.time() - start_time
    cost_total = result.enriched * cost_per

    if result.stopped_reason == "all_keys_exhausted":
        click.echo(f"\nStopped: all API keys exhausted.")
    elif result.stopped_reason == "interrupted":
        click.echo(f"\nInterrupted by user.")

    click.echo(
        f"\nEnrichment complete: {result.enriched:,} enriched, "
        f"{result.failed:,} failed ({result.batches_completed}/{result.batches_total} batches) "
        f"(${cost_total:.2f}, {_format_duration(elapsed)})"
    )

    # 10. Metrics + report (same pattern as before)
    record_metric("profiles_enriched", result.enriched, duration_ms=elapsed * 1000, failed=result.failed)

    report = OperationReport(
        operation="enrich",
        duration_ms=elapsed * 1000,
        counts=OperationCounts(
            total=total,
            succeeded=result.enriched,
            skipped=0,
            failed=result.failed,
        ),
        next_steps=_build_next_steps(skip_embeddings or cfg.enrichment.skip_embeddings),
    )
    report_path = report.save()

    # 11. Next steps
    if skip_embeddings or cfg.enrichment.skip_embeddings:
        click.echo("\nNext steps:")
        click.echo("  -> Run `linkedout embed` to generate embeddings")
        click.echo("  -> Run `linkedout compute-affinity` to calculate affinity scores")
    else:
        click.echo("\nNext steps:")
        click.echo("  -> Run `linkedout compute-affinity` to calculate affinity scores")

    try:
        display = '~/' + str(report_path.relative_to(Path.home()))
    except ValueError:
        display = str(report_path)
    click.echo(f"\nReport saved: {display}")
```

### What's Removed

- The serial `for i, (profile_id, linkedin_url) in enumerate(profiles)` loop
- Per-profile `enrich_profile_sync()` calls
- Per-profile `LinkedOutApifyClient` creation
- Manual `SIGINT` handler (the pipeline handles interruption via state file)
- Per-profile `EnrichmentEventEntity` creation (moved to pipeline or process_batch)

### What's Kept

- `--dry-run` behavior (identical)
- `--limit` behavior (identical)
- Progress reporting (adapted to batch-level via callback)
- `OperationReport` saving
- `record_metric()` call
- `_format_duration()` helper
- `cli_logged` decorator

### What's New

- `--skip-embeddings` flag
- Embedding provider initialization
- `db_session_factory` and `post_enrichment_factory` callables
- Batch-level progress callback

---

## Integration Notes

### How the Pipeline Calls process_batch()

In SP2's `enrich_profiles()`, after fetching and persisting results for a batch, the pipeline needs to process them through `PostEnrichmentService`. The integration pattern:

```python
# Inside the batch processing loop in bulk_enrichment.py:
with db_session_factory() as session:
    service = post_enrichment_factory(session)
    
    # Create enrichment events for this batch
    events = {}
    for profile_id, linkedin_url in batch_profiles:
        if linkedin_url in matched_results:
            event = EnrichmentEventEntity(...)
            session.add(event)
            session.flush()
            events[linkedin_url] = event.id
    
    # Process batch
    results_for_processing = [
        (profile_id, linkedin_url, matched_results[linkedin_url])
        for profile_id, linkedin_url in batch_profiles
        if linkedin_url in matched_results
    ]
    enriched, failed = service.process_batch(
        results_for_processing, events,
        skip_embeddings=skip_embeddings,
        source='bulk_enrichment',
    )
```

This pattern keeps the DB session lifecycle clear: one session per batch, all writes + embeddings within it.

### EnrichmentEvent Creation

Currently, `enrich.py` creates one `EnrichmentEventEntity` per profile before calling `process_enrichment_result()`. In the batch flow, events should be created per-profile within the batch's session, before the `process_batch()` call. This is shown in the integration pattern above.

---

## Verification Checklist

After completing SP3:

1. `linkedout enrich --dry-run` works unchanged
2. `linkedout enrich --limit 5` runs through the batch pipeline
3. `linkedout enrich --skip-embeddings` skips embedding generation
4. State file created at `{data_dir}/enrichment/enrich-state.jsonl`
5. Results saved at `{data_dir}/enrichment/results/{run_id}.json`
6. Lock file prevents concurrent runs
7. Existing tests still pass: `pytest backend/tests/unit/cli/test_enrich_command.py -v`
8. `process_enrichment_result()` unchanged for HTTP controller (extension flow)
