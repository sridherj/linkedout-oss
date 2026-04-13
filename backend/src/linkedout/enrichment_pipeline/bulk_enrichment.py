# SPDX-License-Identifier: Apache-2.0
"""Batched async enrichment pipeline with crash recovery and key rotation.

Orchestrates: chunk profiles -> dispatch Apify runs -> poll -> fetch ->
persist raw results -> process per-profile.  Append-only JSONL state file
enables resume after crash at any point without re-calling Apify for data
already received.
"""
import atexit
import json
import os
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from rapidfuzz import fuzz
from shared.utils.linkedin_url import normalize_linkedin_url

from linkedout.enrichment_pipeline.apify_client import (
    AllKeysExhaustedError,
    ApifyAuthError,
    ApifyCreditExhaustedError,
    ApifyRateLimitError,
    KeyHealthTracker,
    LinkedOutApifyClient,
    get_platform_apify_key,
)
from shared.config import get_config
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="enrichment")

# Maximum age (seconds) before a lock file is considered stale regardless of PID
_LOCK_MAX_AGE_SECONDS = 6 * 60 * 60  # 6 hours

# 429 retry parameters
_RATE_LIMIT_MAX_RETRIES = 3
_RATE_LIMIT_BASE_DELAY = 2  # seconds


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class EnrichmentResult:
    """Summary of a pipeline run."""

    total_profiles: int
    enriched: int
    failed: int
    batches_completed: int
    batches_total: int
    stopped_reason: str | None = None  # "all_keys_exhausted", "interrupted", None


@dataclass
class BatchState:
    """Reconstructed state of a single batch from the state file."""

    batch_idx: int
    urls: list[str]
    run_id: str | None = None
    dataset_id: str | None = None
    run_status: str | None = None
    result_count: int | None = None
    processed_urls: set[str] = field(default_factory=set)
    completed: bool = False


@dataclass
class BatchResumeResult:
    """What to do with a batch based on its state file history."""

    action: str  # 'skip' | 'process' | 'poll' | 'dispatch'
    run_id: str | None = None
    results: list[dict] | None = None
    already_processed: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# State file management
# ---------------------------------------------------------------------------

def _load_state(state_path: Path) -> dict[int, BatchState]:
    """Read state file, reconstruct batch states. Returns {batch_idx: BatchState}."""
    states: dict[int, BatchState] = {}
    if not state_path.exists():
        return states

    with open(state_path, 'r', encoding='utf-8') as f:
        for line_no, raw_line in enumerate(f, 1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                logger.warning('Corrupt state line {}, skipping: {}', line_no, raw_line[:120])
                continue

            event_type = event.get('type')
            batch_idx = event.get('batch_idx')
            if batch_idx is None:
                continue

            if event_type == 'batch_started':
                states[batch_idx] = BatchState(
                    batch_idx=batch_idx,
                    urls=event.get('urls', []),
                    run_id=event.get('run_id'),
                )
            elif event_type == 'batch_fetched' and batch_idx in states:
                states[batch_idx].dataset_id = event.get('dataset_id')
                states[batch_idx].run_status = event.get('run_status')
                states[batch_idx].result_count = event.get('result_count')
            elif event_type == 'profile_processed' and batch_idx in states:
                url = event.get('linkedin_url')
                if url:
                    states[batch_idx].processed_urls.add(url)
            elif event_type == 'batch_completed' and batch_idx in states:
                states[batch_idx].completed = True

    return states


def _append_state(state_path: Path, event: dict) -> None:
    """Append a single event to the state file."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(event, ensure_ascii=False, default=str) + '\n')
        f.flush()


# ---------------------------------------------------------------------------
# Lock file
# ---------------------------------------------------------------------------

@contextmanager
def _acquire_lock(data_dir: Path):
    """Acquire enrichment lock file. Raises SystemExit if already running."""
    lock_path = data_dir / 'enrichment' / 'enrich.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if lock_path.exists():
        try:
            lock_data = json.loads(lock_path.read_text(encoding='utf-8'))
            pid = lock_data.get('pid')
            started_at = lock_data.get('started_at', '')

            # Check age — stale if older than 6 hours regardless of PID
            is_stale_by_age = False
            if started_at:
                try:
                    lock_time = datetime.fromisoformat(started_at)
                    age = (datetime.now(timezone.utc) - lock_time).total_seconds()
                    is_stale_by_age = age > _LOCK_MAX_AGE_SECONDS
                except (ValueError, TypeError):
                    is_stale_by_age = True  # unparseable timestamp → treat as stale

            if is_stale_by_age:
                logger.warning('Stale lock (age > 6h), reclaiming: {}', lock_data)
            elif pid is not None:
                try:
                    os.kill(pid, 0)  # check if PID is alive
                    raise SystemExit(f'Enrichment already running (PID {pid})')
                except OSError:
                    logger.warning('Stale lock (PID {} dead), reclaiming', pid)
            # else: no PID in lock data — treat as stale
        except (json.JSONDecodeError, OSError):
            logger.warning('Corrupt lock file, reclaiming')

    # Write our lock
    lock_data = {
        'pid': os.getpid(),
        'started_at': datetime.now(timezone.utc).isoformat(),
    }
    lock_path.write_text(json.dumps(lock_data), encoding='utf-8')

    def _cleanup():
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass

    atexit.register(_cleanup)

    try:
        yield lock_path
    finally:
        _cleanup()
        atexit.unregister(_cleanup)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _chunk_profiles(
    profiles: list[tuple[str, str]],
    batch_size: int,
) -> list[list[tuple[str, str]]]:
    """Split profiles into batches of batch_size."""
    return [
        profiles[i:i + batch_size]
        for i in range(0, len(profiles), batch_size)
    ]


# ---------------------------------------------------------------------------
# Result matching
# ---------------------------------------------------------------------------

def _match_results(
    batch_urls: list[str],
    apify_results: list[dict],
) -> tuple[dict[str, dict], list[str], dict[str, str]]:
    """Match Apify results to input URLs.

    Returns:
        (matched: {linkedin_url: apify_data},
         missing: [urls not in results],
         redirects: {original_input_url: apify_canonical_url})

    Handles:
        - URL percent-encoding normalization (%xx -> decoded chars)
        - Case-insensitive URL matching
        - Duplicate linkedinUrl in results (first wins)
        - Extra results not in input (ignored)
        - Redirect detection via rapidfuzz slug similarity
    """
    # Build lookup: normalized URL -> apify result (first occurrence wins)
    result_lookup: dict[str, dict] = {}
    for item in apify_results:
        url = item.get('linkedinUrl', '')
        if not url:
            continue
        key = normalize_linkedin_url(url)
        if key and key not in result_lookup:
            result_lookup[key] = item

    matched: dict[str, dict] = {}
    missing: list[str] = []

    # Track which result keys were claimed by exact match
    matched_result_keys: set[str] = set()

    for url in batch_urls:
        key = normalize_linkedin_url(url)
        if key and key in result_lookup:
            matched[url] = result_lookup[key]
            matched_result_keys.add(key)
        else:
            missing.append(url)

    # Fuzzy-match pass: pair unmatched inputs with unmatched results
    redirects: dict[str, str] = {}

    unmatched_results: dict[str, dict] = {
        k: v for k, v in result_lookup.items() if k not in matched_result_keys
    }

    if missing and unmatched_results:
        def _slug(normalized_url: str) -> str:
            return normalized_url.rsplit('/in/', 1)[-1] if '/in/' in normalized_url else normalized_url

        pairs: list[tuple[float, str, str]] = []
        for input_url in missing:
            input_key = normalize_linkedin_url(input_url)
            if not input_key:
                continue
            input_slug = _slug(input_key)
            for result_key in unmatched_results:
                result_slug = _slug(result_key)
                score = fuzz.ratio(input_slug, result_slug)
                pairs.append((score, input_url, result_key))

        # Greedy assignment: highest similarity first
        pairs.sort(key=lambda x: x[0], reverse=True)
        used_inputs: set[str] = set()
        used_results: set[str] = set()

        for score, input_url, result_key in pairs:
            if score < 60:
                break
            if input_url in used_inputs or result_key in used_results:
                continue
            matched[input_url] = unmatched_results[result_key]
            apify_url = unmatched_results[result_key].get('linkedinUrl', '')
            canonical = normalize_linkedin_url(apify_url)
            if canonical:
                redirects[input_url] = canonical
            used_inputs.add(input_url)
            used_results.add(result_key)

        # Update missing: remove successfully paired inputs
        missing = [url for url in missing if url not in used_inputs]

    return matched, missing, redirects


# ---------------------------------------------------------------------------
# Raw result persistence (R1: persist before any DB work)
# ---------------------------------------------------------------------------

def _save_results(results_dir: Path, run_id: str, results: list[dict]) -> Path:
    """Save raw Apify dataset to disk. Returns the file path.

    CRITICAL: This must happen BEFORE any DB processing (R1).
    """
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / f'{run_id}.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, default=str)
    return path


def _load_results(results_dir: Path, run_id: str) -> list[dict] | None:
    """Load previously-saved raw results from disk. Returns None if not found."""
    path = results_dir / f'{run_id}.json'
    if not path.exists():
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def enrich_profiles(
    profiles: list[tuple[str, str]],  # list of (profile_id, linkedin_url)
    db_session_factory=None,               # callable that yields a write session (context manager)
    post_enrichment_factory=None,          # callable(session) -> PostEnrichmentService
    embedding_provider=None,
    key_tracker: KeyHealthTracker | None = None,
    data_dir: str | Path | None = None,
    skip_embeddings: bool = False,
    on_progress: Callable | None = None,  # callback(enriched, failed, total, batch_idx)
) -> EnrichmentResult:
    """Run the batched enrichment pipeline.

    Caller passes everything needed — the pipeline doesn't reach into global
    state. This makes testing straightforward (inject fakes for everything).
    """
    if not profiles:
        return EnrichmentResult(
            total_profiles=0, enriched=0, failed=0,
            batches_completed=0, batches_total=0,
        )

    # Resolve data_dir
    if data_dir is None:
        data_dir = Path(get_config().data_dir)
    else:
        data_dir = Path(data_dir)

    enrichment_dir = data_dir / 'enrichment'
    results_dir = enrichment_dir / 'results'
    state_path = enrichment_dir / 'enrich-state.jsonl'
    enrichment_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    cfg = get_config().enrichment
    batch_size = cfg.max_batch_size
    max_parallel_batches = cfg.max_parallel_batches

    # Build profile_id lookup for later use
    profile_id_by_url: dict[str, str] = {}
    for pid, url in profiles:
        profile_id_by_url[url] = pid

    total_enriched = 0
    total_failed = 0
    batches_completed = 0
    stopped_reason: str | None = None

    with _acquire_lock(data_dir):
        existing_state = _load_state(state_path)
        batches = _chunk_profiles(profiles, batch_size)
        batches_total = len(batches)

        pending = deque(enumerate(batches))  # [(batch_idx, batch_profiles), ...]
        inflight: dict[int, tuple[str, list[str], float]] = {}  # {batch_idx: (run_id, batch_urls, dispatch_time)}

        while pending or inflight:
            # ── Fill slots ──
            while len(inflight) < max_parallel_batches and pending:
                batch_idx, batch_profiles = pending.popleft()
                batch_urls = [url for _, url in batch_profiles]

                resume = _check_batch_resume(batch_idx, batch_urls, existing_state, results_dir)

                if resume.action == 'skip':
                    # Already completed — count and continue
                    logger.info('Batch {} already completed, skipping', batch_idx)
                    batches_completed += 1
                    total_enriched += len(resume.already_processed)
                    if on_progress:
                        on_progress(total_enriched, total_failed, len(profiles), batch_idx)
                    continue

                elif resume.action == 'process':
                    # Fetched but not fully processed — process from disk
                    logger.info(
                        'Batch %d fetched but not fully processed (%d/%d), resuming',
                        batch_idx, len(resume.already_processed), len(batch_urls),
                    )
                    enriched, failed = _process_batch_results(
                        batch_idx=batch_idx,
                        batch_urls=batch_urls,
                        apify_results=resume.results,
                        profile_id_by_url=profile_id_by_url,
                        already_processed=resume.already_processed,
                        state_path=state_path,
                        db_session_factory=db_session_factory,
                        post_enrichment_factory=post_enrichment_factory,
                        skip_embeddings=skip_embeddings,
                    )
                    total_enriched += enriched
                    total_failed += failed
                    _append_state(state_path, {
                        'type': 'batch_completed',
                        'batch_idx': batch_idx,
                        'enriched': enriched,
                        'failed': failed,
                    })
                    batches_completed += 1
                    if on_progress:
                        on_progress(total_enriched, total_failed, len(profiles), batch_idx)
                    continue

                elif resume.action == 'poll':
                    # Started but not fetched — add to inflight for polling (NO re-dispatch)
                    logger.info('Batch {} resuming poll (run {})', batch_idx, resume.run_id)
                    inflight[batch_idx] = (resume.run_id, batch_urls, time.time())

                else:  # 'dispatch'
                    run_id = _dispatch_batch(
                        batch_idx=batch_idx,
                        batch_urls=batch_urls,
                        key_tracker=key_tracker,
                        state_path=state_path,
                    )
                    if run_id is None:
                        stopped_reason = 'all_keys_exhausted'
                        break
                    inflight[batch_idx] = (run_id, batch_urls, time.time())

            # Break out of outer while if all keys exhausted during fill
            if stopped_reason:
                break

            # ── Poll all inflight ──
            if not inflight:
                continue

            # Any healthy key can poll any run (Decision #2)
            api_key = _get_key(key_tracker)
            if api_key is None and inflight:
                # All keys dead — can't poll. Inflight batches stay in state for resume.
                stopped_reason = 'all_keys_exhausted'
                break
            client = LinkedOutApifyClient(api_key)

            for batch_idx in list(inflight):
                run_id, batch_urls, dispatch_time = inflight[batch_idx]
                try:
                    result = client.check_run_status(run_id)
                except Exception:
                    # Per-batch error isolation — log, retry next poll cycle
                    logger.warning('Batch {} poll error for run {}, will retry', batch_idx, run_id)
                    continue

                if result is not None:
                    status, dataset_id = result
                    logger.info('Batch {} run {} finished: status={}', batch_idx, run_id, status)

                    # Disk cache before fetch (Decision #3)
                    results = _load_results(results_dir, run_id)
                    if results is None:
                        try:
                            results = client.fetch_results(dataset_id)
                        except Exception:
                            # Fetch failed — leave in inflight, retry next cycle
                            logger.warning('Batch {} fetch failed for run {}, will retry', batch_idx, run_id)
                            continue
                    _save_results(results_dir, run_id, results)

                    _append_state(state_path, {
                        'type': 'batch_fetched',
                        'batch_idx': batch_idx,
                        'run_id': run_id,
                        'dataset_id': dataset_id,
                        'run_status': status,
                        'result_count': len(results),
                    })

                    # Get already_processed from state (may have partial processing from prior crash)
                    batch_state = existing_state.get(batch_idx)
                    already_processed = batch_state.processed_urls if batch_state else set()

                    enriched, failed = _process_batch_results(
                        batch_idx=batch_idx,
                        batch_urls=batch_urls,
                        apify_results=results,
                        profile_id_by_url=profile_id_by_url,
                        already_processed=already_processed,
                        state_path=state_path,
                        db_session_factory=db_session_factory,
                        post_enrichment_factory=post_enrichment_factory,
                        skip_embeddings=skip_embeddings,
                    )
                    total_enriched += enriched
                    total_failed += failed
                    _append_state(state_path, {
                        'type': 'batch_completed',
                        'batch_idx': batch_idx,
                        'enriched': enriched,
                        'failed': failed,
                    })
                    batches_completed += 1
                    if on_progress:
                        on_progress(total_enriched, total_failed, len(profiles), batch_idx)

                    del inflight[batch_idx]

            # ── Timeout check ──
            poll_timeout = cfg.run_poll_timeout_seconds
            for batch_idx in list(inflight):
                run_id, batch_urls, dispatch_time = inflight[batch_idx]
                if time.time() - dispatch_time > poll_timeout:
                    logger.warning(
                        'Batch {} poll timed out (run {}). Results may still arrive — '
                        'will attempt recovery on next run.',
                        batch_idx, run_id,
                    )
                    del inflight[batch_idx]

            # ── Sleep before next poll cycle ──
            if inflight:
                time.sleep(cfg.run_poll_interval_seconds)

    return EnrichmentResult(
        total_profiles=len(profiles),
        enriched=total_enriched,
        failed=total_failed,
        batches_completed=batches_completed,
        batches_total=batches_total,
        stopped_reason=stopped_reason,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_key(key_tracker: KeyHealthTracker | None) -> str | None:
    """Get an API key from the tracker or platform default. Returns None if all exhausted."""
    try:
        if key_tracker is not None:
            return key_tracker.next_key()
        return get_platform_apify_key()
    except AllKeysExhaustedError:
        logger.error('All Apify API keys are exhausted or invalid')
        return None


def _check_batch_resume(
    batch_idx: int,
    batch_urls: list[str],
    existing_state: dict[int, BatchState],
    results_dir: Path,
) -> BatchResumeResult:
    """Determine what action to take for a batch based on prior state.

    Checks state file history and disk cache to classify the batch into one of:
    - skip: fully completed in a prior run
    - process: results fetched and on disk, but not all profiles processed
    - poll: dispatched to Apify but results not fetched yet
    - dispatch: not started, needs fresh Apify dispatch
    """
    batch_state = existing_state.get(batch_idx)

    # ── Not started ──
    if batch_state is None:
        return BatchResumeResult(action='dispatch')

    # ── Already completed ──
    if batch_state.completed:
        return BatchResumeResult(
            action='skip',
            already_processed=batch_state.processed_urls,
        )

    # ── Fetched but not fully processed ──
    if batch_state.dataset_id and batch_state.run_id:
        saved_results = _load_results(results_dir, batch_state.run_id)
        if saved_results is not None:
            return BatchResumeResult(
                action='process',
                run_id=batch_state.run_id,
                results=saved_results,
                already_processed=batch_state.processed_urls,
            )
        else:
            # Results file missing — need to re-fetch via polling
            # (dataset_id is set, so Apify completed, but we lost the file)
            return BatchResumeResult(
                action='poll',
                run_id=batch_state.run_id,
                already_processed=batch_state.processed_urls,
            )

    # ── Started but not fetched ──
    if batch_state.run_id:
        return BatchResumeResult(
            action='poll',
            run_id=batch_state.run_id,
            already_processed=batch_state.processed_urls,
        )

    # ── Defensive: state exists but no run_id (shouldn't happen) ──
    return BatchResumeResult(action='dispatch')


def _dispatch_batch(
    batch_idx: int,
    batch_urls: list[str],
    key_tracker: KeyHealthTracker | None,
    state_path: Path,
) -> str | None:
    """Dispatch a batch to Apify. Returns run_id or None if all keys exhausted.

    Handles 402/401/403 by rotating keys, 429 by exponential backoff.
    """
    retries_429 = 0

    while True:
        api_key = _get_key(key_tracker)
        if api_key is None:
            return None

        client = LinkedOutApifyClient(api_key)
        try:
            run_id = client.enrich_profiles_async(batch_urls)
            _append_state(state_path, {
                'type': 'batch_started',
                'batch_idx': batch_idx,
                'run_id': run_id,
                'urls': batch_urls,
                'started_at': datetime.now(timezone.utc).isoformat(),
            })
            logger.info('Batch {} dispatched: run_id={}, urls={}', batch_idx, run_id, len(batch_urls))
            return run_id

        except ApifyCreditExhaustedError:
            logger.warning('Batch {}: key …{} credits exhausted (402), rotating', batch_idx, api_key[-4:])
            if key_tracker is not None:
                key_tracker.mark_exhausted(api_key)
            continue

        except ApifyAuthError:
            logger.warning('Batch {}: key …{} auth failed (401/403), rotating', batch_idx, api_key[-4:])
            if key_tracker is not None:
                key_tracker.mark_invalid(api_key)
            continue

        except ApifyRateLimitError:
            retries_429 += 1
            if retries_429 > _RATE_LIMIT_MAX_RETRIES:
                logger.error('Batch {}: rate limit retries exceeded', batch_idx)
                return None
            delay = _RATE_LIMIT_BASE_DELAY * (2 ** (retries_429 - 1))
            logger.warning('Batch {}: rate limited (429), backing off {}s', batch_idx, delay)
            time.sleep(delay)
            continue


def _process_batch_results(
    batch_idx: int,
    batch_urls: list[str],
    apify_results: list[dict],
    profile_id_by_url: dict[str, str],
    already_processed: set[str],
    state_path: Path,
    db_session_factory=None,
    post_enrichment_factory=None,
    skip_embeddings: bool = False,
) -> tuple[int, int]:
    """Process Apify results for a batch. Returns (enriched_count, failed_count).

    Uses PostEnrichmentService.process_batch() for batch embedding and archiving
    when db_session_factory and post_enrichment_factory are provided.
    """
    matched, _missing, redirects = _match_results(batch_urls, apify_results)
    enriched = 0
    failed = 0

    # Separate already-processed, matched, and missing
    to_process: list[tuple[str, str, dict]] = []
    for url in batch_urls:
        if url in already_processed:
            enriched += 1
            continue

        profile_id = profile_id_by_url.get(url)

        if url in matched:
            to_process.append((profile_id, url, matched[url]))
        else:
            failed += 1
            logger.warning('Batch {}: no result for {}', batch_idx, url)
            _append_state(state_path, {
                'type': 'profile_processed',
                'batch_idx': batch_idx,
                'linkedin_url': url,
                'profile_id': profile_id,
                'status': 'failed',
                'error': 'missing_from_results',
            })

    if to_process and db_session_factory is not None and post_enrichment_factory is not None:
        try:
            with db_session_factory() as session:
                service = post_enrichment_factory(session)
                batch_enriched, batch_failed = service.process_batch(
                    to_process,
                    enrichment_event_ids={},
                    skip_embeddings=skip_embeddings,
                    source='bulk_enrichment',
                    redirects=redirects,
                )
                session.commit()
            enriched += batch_enriched
            failed += batch_failed
        except Exception:
            logger.exception('Batch {} process_batch() failed entirely', batch_idx)
            failed += len(to_process)

        for profile_id, url, _ in to_process:
            _append_state(state_path, {
                'type': 'profile_processed',
                'batch_idx': batch_idx,
                'linkedin_url': url,
                'profile_id': profile_id,
                'status': 'enriched',
            })
    elif to_process:
        # No DB factory — just mark as enriched (testing / dry-run mode)
        enriched += len(to_process)
        for profile_id, url, _ in to_process:
            _append_state(state_path, {
                'type': 'profile_processed',
                'batch_idx': batch_idx,
                'linkedin_url': url,
                'profile_id': profile_id,
                'status': 'enriched',
            })

    return enriched, failed


# ---------------------------------------------------------------------------
# Recovery: collect results from incomplete prior runs
# ---------------------------------------------------------------------------

@dataclass
class RecoverySummary:
    """Result of a pre-run recovery sweep."""

    recovered: int = 0           # profiles successfully processed
    failed: int = 0              # profiles in FAILED/ABORTED Apify batches
    still_running: int = 0       # profiles in batches still running on Apify
    batches_recovered: int = 0   # batches fully recovered


def check_recoverable_batches(
    data_dir: str | Path,
    api_key: str | None = None,
) -> RecoverySummary:
    """Read-only check: how many profiles have uncollected Apify results?

    Checks the state file for incomplete batches and queries Apify for their
    status. Does NOT fetch results or write to the state file.
    """
    data_dir = Path(data_dir)
    state_path = data_dir / 'enrichment' / 'enrich-state.jsonl'
    existing_state = _load_state(state_path)

    incomplete = {
        idx: bs for idx, bs in existing_state.items()
        if not bs.completed and bs.run_id
    }
    if not incomplete:
        return RecoverySummary()

    if api_key is None:
        try:
            api_key = get_platform_apify_key()
        except (ValueError, AllKeysExhaustedError):
            # Can't check Apify — report all incomplete as unknown
            total_urls = sum(len(bs.urls) for bs in incomplete.values())
            return RecoverySummary(still_running=total_urls)

    client = LinkedOutApifyClient(api_key)
    summary = RecoverySummary()

    for batch_idx, batch_state in incomplete.items():
        n_urls = len(batch_state.urls)
        try:
            result = client.check_run_status(batch_state.run_id)
        except Exception:
            summary.still_running += n_urls
            continue

        if result is None:
            # Still running
            summary.still_running += n_urls
        else:
            status, _dataset_id = result
            if status == 'SUCCEEDED':
                summary.recovered += n_urls
            else:
                summary.failed += n_urls

    return summary


def recover_incomplete_batches(
    data_dir: str | Path,
    db_session_factory=None,
    post_enrichment_factory=None,
    skip_embeddings: bool = False,
    api_key: str | None = None,
) -> RecoverySummary:
    """Recover results from incomplete batches in a prior run.

    Scans the state file for batches that were dispatched (batch_started) but
    never completed (no batch_completed).  For each, checks Apify status and
    fetches/processes results if the run succeeded.

    Uses URLs stored in the state file's batch_started events — not the current
    DB query — so recovery works even when the unenriched profile list has
    changed between runs.

    After all incomplete batches are resolved (none still running), the state
    file is rotated to ``.jsonl.prev`` so the next run starts clean.
    """
    data_dir = Path(data_dir)
    enrichment_dir = data_dir / 'enrichment'
    results_dir = enrichment_dir / 'results'
    state_path = enrichment_dir / 'enrich-state.jsonl'

    existing_state = _load_state(state_path)

    incomplete = {
        idx: bs for idx, bs in existing_state.items()
        if not bs.completed and bs.run_id
    }
    if not incomplete:
        # Nothing to recover — rotate if all completed
        if existing_state and all(bs.completed for bs in existing_state.values()):
            _rotate_state(state_path)
        return RecoverySummary()

    if api_key is None:
        try:
            api_key = get_platform_apify_key()
        except (ValueError, AllKeysExhaustedError):
            logger.warning('Cannot recover: no Apify API key available')
            return RecoverySummary()

    client = LinkedOutApifyClient(api_key)
    summary = RecoverySummary()

    # Build profile_id lookup from the state file URLs
    # We need profile_ids to process results — query DB for the URLs we care about
    all_recovery_urls: set[str] = set()
    for bs in incomplete.values():
        all_recovery_urls.update(bs.urls)

    profile_id_by_url: dict[str, str] = {}
    if db_session_factory is not None and all_recovery_urls:
        try:
            with db_session_factory() as session:
                from sqlalchemy import text
                rows = session.execute(text(
                    "SELECT id, linkedin_url FROM crawled_profile "
                    "WHERE is_active = true"
                )).fetchall()
                for row in rows:
                    if row[1] in all_recovery_urls:
                        profile_id_by_url[row[1]] = row[0]
        except Exception:
            logger.exception('Failed to query profile IDs for recovery')
            return RecoverySummary()

    for batch_idx, batch_state in incomplete.items():
        n_urls = len(batch_state.urls)
        run_id = batch_state.run_id

        try:
            result = client.check_run_status(run_id)
        except Exception:
            logger.warning('Batch {} recovery: poll failed for run {}', batch_idx, run_id)
            summary.still_running += n_urls
            continue

        if result is None:
            logger.info('Batch {} recovery: run {} still running, skipping', batch_idx, run_id)
            summary.still_running += n_urls
            continue

        status, dataset_id = result

        if status != 'SUCCEEDED':
            logger.warning('Batch {} recovery: run {} status={}, marking failed', batch_idx, run_id, status)
            _append_state(state_path, {
                'type': 'batch_completed', 'batch_idx': batch_idx,
                'enriched': 0, 'failed': n_urls,
            })
            summary.failed += n_urls
            continue

        # SUCCEEDED — fetch and process
        logger.info('Batch {} recovery: run {} succeeded, fetching {} results', batch_idx, run_id, n_urls)

        # Try disk cache first, then Apify
        results_data = _load_results(results_dir, run_id)
        if results_data is None:
            try:
                results_data = client.fetch_results(dataset_id)
                _save_results(results_dir, run_id, results_data)
            except Exception:
                logger.exception('Batch {} recovery: fetch failed for run {}', batch_idx, run_id)
                summary.still_running += n_urls  # might succeed later
                continue

        _append_state(state_path, {
            'type': 'batch_fetched', 'batch_idx': batch_idx,
            'run_id': run_id, 'dataset_id': dataset_id,
            'run_status': status, 'result_count': len(results_data),
        })

        enriched, failed = _process_batch_results(
            batch_idx=batch_idx,
            batch_urls=batch_state.urls,
            apify_results=results_data,
            profile_id_by_url=profile_id_by_url,
            already_processed=batch_state.processed_urls,
            state_path=state_path,
            db_session_factory=db_session_factory,
            post_enrichment_factory=post_enrichment_factory,
            skip_embeddings=skip_embeddings,
        )

        _append_state(state_path, {
            'type': 'batch_completed', 'batch_idx': batch_idx,
            'enriched': enriched, 'failed': failed,
        })

        summary.recovered += enriched
        summary.failed += failed
        summary.batches_recovered += 1

    # Rotate state file if everything is resolved
    if summary.still_running == 0 and state_path.exists():
        _rotate_state(state_path)

    return summary


def _rotate_state(state_path: Path) -> None:
    """Rotate state file to .jsonl.prev so next run starts clean."""
    prev = state_path.with_suffix('.jsonl.prev')
    if prev.exists():
        prev.unlink()
    state_path.rename(prev)
