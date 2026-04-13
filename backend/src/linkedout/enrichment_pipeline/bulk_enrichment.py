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

        for batch_idx, batch_profiles in enumerate(batches):
            batch_urls = [url for _, url in batch_profiles]
            batch_state = existing_state.get(batch_idx)

            # ── Already completed ──────────────────────────────
            if batch_state and batch_state.completed:
                logger.info('Batch {} already completed, skipping', batch_idx)
                # Reconstruct counts from state events — we don't store them
                # on BatchState directly, so count processed_urls
                batches_completed += 1
                # We can't know exact enriched/failed from state alone without
                # re-reading events, so count processed as enriched (conservative)
                total_enriched += len(batch_state.processed_urls)
                if on_progress:
                    on_progress(total_enriched, total_failed, len(profiles), batch_idx)
                continue

            # ── Fetched but not fully processed (resume processing) ──
            if batch_state and batch_state.dataset_id and batch_state.run_id:
                logger.info(
                    'Batch %d fetched but not fully processed (%d/%d), resuming processing',
                    batch_idx, len(batch_state.processed_urls), len(batch_urls),
                )
                saved_results = _load_results(results_dir, batch_state.run_id)
                if saved_results is not None:
                    enriched, failed = _process_batch_results(
                        batch_idx=batch_idx,
                        batch_urls=batch_urls,
                        apify_results=saved_results,
                        profile_id_by_url=profile_id_by_url,
                        already_processed=batch_state.processed_urls,
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
                else:
                    # Results file missing — need to re-fetch
                    logger.warning(
                        'Batch %d results file missing for run %s, will re-fetch',
                        batch_idx, batch_state.run_id,
                    )
                    # Fall through to poll+fetch path below
                    run_id = batch_state.run_id
                    api_key = _get_key(key_tracker)
                    if api_key is None:
                        stopped_reason = 'all_keys_exhausted'
                        break
                    client = LinkedOutApifyClient(api_key)
                    try:
                        _status, _ds_id, results = _poll_fetch_save(
                            client, run_id, results_dir, batch_idx, state_path,
                        )
                    except Exception as e:
                        logger.error('Batch {} fetch failed: {}', batch_idx, e)
                        continue

                    enriched, failed = _process_batch_results(
                        batch_idx=batch_idx,
                        batch_urls=batch_urls,
                        apify_results=results,
                        profile_id_by_url=profile_id_by_url,
                        already_processed=batch_state.processed_urls,
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

            # ── Started but not fetched (resume polling) ──────
            if batch_state and batch_state.run_id and not batch_state.dataset_id:
                logger.info('Batch {} started (run {}) but not fetched, resuming poll',
                            batch_idx, batch_state.run_id)
                run_id = batch_state.run_id
                api_key = _get_key(key_tracker)
                if api_key is None:
                    stopped_reason = 'all_keys_exhausted'
                    break
                client = LinkedOutApifyClient(api_key)
                try:
                    _status, _ds_id, results = _poll_fetch_save(
                        client, run_id, results_dir, batch_idx, state_path,
                    )
                except Exception as e:
                    logger.error('Batch {} poll/fetch failed: {}', batch_idx, e)
                    continue

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
                continue

            # ── Not started — dispatch new batch ──────────────
            run_id = _dispatch_batch(
                batch_idx=batch_idx,
                batch_urls=batch_urls,
                key_tracker=key_tracker,
                state_path=state_path,
            )
            if run_id is None:
                stopped_reason = 'all_keys_exhausted'
                break

            # Get a client for polling (may use different key)
            api_key = _get_key(key_tracker)
            if api_key is None:
                stopped_reason = 'all_keys_exhausted'
                break
            client = LinkedOutApifyClient(api_key)

            try:
                _status, _ds_id, results = _poll_fetch_save(
                    client, run_id, results_dir, batch_idx, state_path,
                )
            except Exception as e:
                logger.error('Batch {} poll/fetch failed: {}', batch_idx, e)
                continue

            enriched, failed = _process_batch_results(
                batch_idx=batch_idx,
                batch_urls=batch_urls,
                apify_results=results,
                profile_id_by_url=profile_id_by_url,
                already_processed=set(),
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


def _poll_fetch_save(
    client: LinkedOutApifyClient,
    run_id: str,
    results_dir: Path,
    batch_idx: int,
    state_path: Path,
) -> tuple[str, str, list[dict]]:
    """Poll for run completion, fetch results, save to disk.

    Returns (run_status, dataset_id, results).
    Does NOT write batch_fetched to state if fetch fails (enables clean resume).
    """
    status, dataset_id = client.poll_run_safe(run_id)
    logger.info('Batch {} run {} finished: status={}, dataset={}', batch_idx, run_id, status, dataset_id)

    results = client.fetch_results(dataset_id)

    # R1: persist raw results to disk BEFORE any other processing
    _save_results(results_dir, run_id, results)

    _append_state(state_path, {
        'type': 'batch_fetched',
        'batch_idx': batch_idx,
        'run_id': run_id,
        'dataset_id': dataset_id,
        'run_status': status,
        'result_count': len(results),
    })

    return status, dataset_id, results


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
