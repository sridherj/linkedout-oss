# Sub-Phase 4: `linkedout embed` CLI Command + Integration Tests

**Phase:** 5 — Embedding Provider Abstraction
**Plan tasks:** 5H (CLI Command), Testing Strategy
**Dependencies:** sp3 (Factory + Callers), sp2d (Progress Tracking)
**Blocks:** None (final sub-phase)
**Can run in parallel with:** None

## Objective
Wire the embedding pipeline into the `linkedout embed` CLI command with progress bar, resumability, dry-run mode, and the operation result pattern. Then write integration tests that verify the full end-to-end flow.

## Context
- Read shared context: `docs/execution/phase-05/_shared_context.md`
- Read plan (5H section + Testing Strategy): `docs/plan/phase-05-embedding-abstraction.md`
- Read CLI surface decision: `docs/decision/cli-surface.md` (the `linkedout embed` contract)
- Read logging strategy: `docs/decision/logging-observability-strategy.md` (operation result pattern, report format)
- Read updated generate_embeddings.py (from sp3): `backend/src/dev_tools/generate_embeddings.py`
- Read progress tracking (from sp2d): `backend/src/utilities/embedding_progress.py`
- Read factory (from sp3): `backend/src/utilities/llm_manager/embedding_factory.py`
- Check where CLI commands are registered: look for the Click group in `backend/src/dev_tools/cli.py` or wherever the `linkedout` namespace is defined

## Deliverables

### 1. Refactor `backend/src/dev_tools/generate_embeddings.py` into `linkedout embed`

This file already has the core logic (updated in sp3 to use the provider abstraction). Now restructure it as the `linkedout embed` CLI command.

**CLI contract (from cli-surface.md):**
```
linkedout embed [OPTIONS]

Options:
  --provider PROVIDER   Embedding provider: openai, local (default: from config)
  --dry-run             Report what would be embedded, do not run
  --resume              Resume from last checkpoint (default: true)
  --force               Re-embed all profiles, even those with current embeddings
```

**Implementation flow:**
```python
@click.command('embed')
@click.option('--provider', type=click.Choice(['openai', 'local']), default=None,
              help='Embedding provider (default: from config)')
@click.option('--dry-run', is_flag=True, help='Report what would be embedded, do not run')
@click.option('--force', is_flag=True, help='Re-embed all profiles')
def embed_command(provider, dry_run, force):
    """Generate vector embeddings for profile search."""

    # 1. Get provider
    embedding_provider = get_embedding_provider(provider=provider)
    column_name = get_embedding_column_name(embedding_provider)

    # 2. Check progress file
    progress_path = get_progress_path()
    progress = None if force else EmbeddingProgress.load(progress_path)

    if progress and progress.status == "completed" and not force:
        click.echo("All profiles already embedded. Use --force to re-embed.")
        return

    # 3. If --force, delete progress file and optionally clear target column
    if force:
        progress_path.unlink(missing_ok=True)
        progress = None
        # Clear the target embedding column for all rows
        # (so they get re-embedded)

    # 4. Fetch profiles needing embeddings
    #    If resuming: WHERE id > last_processed_id AND {column} IS NULL
    #    If fresh: WHERE has_enriched_data = TRUE AND {column} IS NULL

    # 5. Dry-run: report counts and exit
    if dry_run:
        # Print: total profiles, profiles needing embeddings, provider, dimension, estimated time, estimated cost
        return

    # 6. Initialize progress
    progress = EmbeddingProgress(
        provider=provider_name,
        model=embedding_provider.model_name(),
        dimension=embedding_provider.dimension(),
        total_profiles=total_count,
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    # 7. Print header
    click.echo(f"Embedding profiles with {embedding_provider.model_name()} ({embedding_provider.dimension()}d, {provider_name})...")
    click.echo(f"Estimated time: {embedding_provider.estimate_time(total_count)}")
    cost = embedding_provider.estimate_cost(total_count)
    if cost:
        click.echo(f"Estimated cost: {cost}")

    # 8. Process in batches with progress bar
    with click.progressbar(length=total_count, label='Embedding') as bar:
        for batch in batched(profiles, batch_size):
            texts = [build_embedding_text(p) for p in batch]
            vectors = embedding_provider.embed(texts)
            # Write to DB (correct column)
            # Update progress
            progress.mark_batch_complete(batch[-1]['id'], len(batch))
            progress.save(progress_path)
            bar.update(len(batch))

    # 9. Mark complete
    progress.mark_completed()
    progress.save(progress_path)

    # 10. Operation result pattern output
    click.echo(f"\nResults:")
    click.echo(f"  Embedded:   {embedded_count:,} profiles")
    click.echo(f"  Skipped:    {skipped_count:,} (already embedded)")
    click.echo(f"  Failed:     {failed_count:,}")
    click.echo(f"  Provider:   {embedding_provider.model_name()} ({embedding_provider.dimension()}d)")
    click.echo(f"  Duration:   {format_duration(elapsed)}")
    click.echo(f"\nNext steps:")
    click.echo(f"  -> Run `linkedout compute-affinity` to update affinity scores")
    click.echo(f"\nReport saved: {report_path}")

    # 11. Write report artifact
    write_operation_report(report_path, ...)
```

**Report artifact** (`~/linkedout-data/reports/embed-{provider}-YYYYMMDD-HHMMSS.json`):
```json
{
  "operation": "embed",
  "timestamp": "2026-04-07T14:23:05Z",
  "duration_ms": 402000,
  "provider": "nomic-embed-text-v1.5",
  "dimension": 768,
  "counts": {
    "total": 4012,
    "embedded": 4000,
    "skipped": 12,
    "failed": 0
  },
  "coverage_gaps": [],
  "failures": [],
  "next_steps": ["Run `linkedout compute-affinity` to update affinity scores"]
}
```

**Logging integration:**
- Use loguru with `component="cli"`, `operation="embed"`
- Log to `~/linkedout-data/logs/cli.log`
- Write metrics event to `~/linkedout-data/metrics/daily/YYYY-MM-DD.jsonl`

### 2. Register CLI Command

Check `backend/src/dev_tools/cli.py` (or wherever the `linkedout` Click group is defined). Register the `embed` command:

```python
# In the CLI group
cli.add_command(embed_command, 'embed')
```

If the `linkedout` CLI namespace doesn't exist yet (depends on Phase 6 progress), register under the existing CLI group for now.

### 3. Handle Edge Cases

- **0 profiles:** Print "No profiles need embedding." and exit cleanly
- **All already embedded (no --force):** Print "All profiles already embedded with {model}. Use --force to re-embed." and exit
- **Resume with different provider:** If progress file says `provider=openai` but current config is `local`, warn and start fresh (don't resume a different provider's state)
- **Network failure during local model download:** Clear error message with instructions to retry
- **OpenAI API error during batch:** Log the error, save progress, exit with error status. User can resume later.
- **Keyboard interrupt (Ctrl+C):** Save progress before exiting (use `try/except KeyboardInterrupt` or signal handler)

### 4. Integration Tests

**`backend/tests/integration/test_embed_command.py`** (NEW):

These tests use a real database but mock the embedding API.

| Test | What It Validates |
|------|-------------------|
| `test_embed_openai_e2e` | Create profiles, run embed with mocked OpenAI, verify `embedding_openai` column populated, metadata set |
| `test_embed_local_e2e` | Create profiles, run embed with mocked local model, verify `embedding_nomic` column populated |
| `test_embed_dry_run` | `--dry-run` reports counts without modifying DB |
| `test_embed_force` | `--force` re-embeds profiles that already have embeddings |
| `test_embed_resume` | Embed 50% of profiles, save progress, call embed again, verify it resumes (no duplicates) |
| `test_embed_idempotent` | Run embed twice on fully-embedded DB, second run is a no-op |
| `test_embed_provider_switch` | Embed with OpenAI, switch config to local, embed again, both columns have values |
| `test_search_after_embed` | Embed profiles, then run `search_profiles()` — verify results come back ranked by similarity |
| `test_embed_zero_profiles` | Run embed on empty DB — clean exit with message |

**Use Click's `CliRunner` for testing CLI commands:**
```python
from click.testing import CliRunner
runner = CliRunner()
result = runner.invoke(embed_command, ['--dry-run'])
assert result.exit_code == 0
```

### 5. Unit Tests: `backend/tests/unit/cli/test_embed_command.py` (NEW)

Lighter-weight tests that don't need a real DB:
- `--dry-run` flag is recognized
- `--force` flag is recognized
- `--provider openai` and `--provider local` are accepted
- `--provider invalid` is rejected
- Output format matches operation result pattern (check for "Results:", "Next steps:", "Report saved:")

## Verification
1. `linkedout embed --dry-run` reports counts correctly
2. `linkedout embed --provider openai` embeds with OpenAI (mocked in tests)
3. `linkedout embed --provider local` embeds with nomic (mocked in tests)
4. `linkedout embed --force` re-embeds all profiles
5. Interrupt mid-run, resume — no duplicates, correct count
6. Progress file created at `~/linkedout-data/state/embedding_progress.json`
7. Report artifact created at `~/linkedout-data/reports/embed-*.json`
8. `cd backend && uv run pytest tests/unit/cli/test_embed_command.py -v` passes
9. `cd backend && uv run pytest tests/integration/test_embed_command.py -v` passes
10. `cd backend && uv run pytest tests/ -x --timeout=120` — all tests pass (unit + integration)

## Exit Criteria (Phase 5 Complete)
After sp4, verify ALL of these from the phase plan:
- [ ] Both `openai` and `local` providers produce embeddings and write to the correct pgvector column
- [ ] `linkedout embed` is resumable: interrupt mid-run, restart, no duplicates
- [ ] `linkedout embed` is idempotent: running on fully-embedded DB is a no-op
- [ ] `linkedout embed --force` re-embeds all profiles
- [ ] `linkedout embed --dry-run` reports counts without writing
- [ ] Progress tracked in `~/linkedout-data/state/embedding_progress.json`
- [ ] Embedding output reports written to `~/linkedout-data/reports/`
- [ ] Switching providers works without data loss
- [ ] Semantic search queries the correct column for the active provider
- [ ] Affinity scoring reads from the correct embedding column
- [ ] No `EmbeddingClient` instantiated directly outside the OpenAI provider
- [ ] All existing tests pass (no regressions)
- [ ] New unit + integration tests pass

## Notes
- The CLI command absorbs most of `generate_embeddings.py`'s logic but restructures it significantly. Don't try to preserve the old code structure — rewrite for clarity.
- The old Batch API flags (`--batch-api`, `--resume-batch-id`, `--fail-and-push`) are OpenAI-specific. They can be kept as hidden flags or removed in favor of the simpler `--provider openai` + `--force` interface. Decision: keep `--batch` as an OpenAI-specific flag for power users. Remove `--resume-batch-id` and `--fail-and-push` (too complex for OSS v1).
- The `--resume` flag defaults to `true` — embedding is resumable by default. The flag exists only for explicitness.
- Click's `progressbar` is sufficient for v1. No need for `rich` or `tqdm`.
