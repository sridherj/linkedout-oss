# SPDX-License-Identifier: Apache-2.0
"""Query logging module that records every skill-driven query as JSONL.

All writes go to ~/linkedout-data/queries/YYYY-MM-DD.jsonl. Thread-safe and
process-safe via fcntl.flock() advisory locking.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from nanoid import generate as nanoid_generate

from linkedout.query_history.session_manager import start_new_session

# Try to import Phase 3 logging infrastructure; fall back to stdlib
try:
    from shared.utilities.logger import get_logger as _get_logger

    _logger = _get_logger(component='skill', operation='query')
except ImportError:
    _logger = logging.getLogger(__name__)

# Try to import Phase 3 metrics infrastructure; skip if unavailable
try:
    from shared.utilities.metrics import record_metric as _record_metric
except ImportError:
    _record_metric = None


def get_queries_dir() -> Path:
    """Resolve ~/linkedout-data/queries/ with LINKEDOUT_DATA_DIR override."""
    data_dir = os.environ.get('LINKEDOUT_DATA_DIR', os.path.expanduser('~/linkedout-data'))
    return Path(os.path.expanduser(data_dir)) / 'queries'


def get_today_file() -> Path:
    """Resolve today's JSONL file path (YYYY-MM-DD.jsonl)."""
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    return get_queries_dir() / f'{today}.jsonl'


def log_query(
    query_text: str,
    query_type: str = 'general',
    result_count: int = 0,
    duration_ms: int = 0,
    model_used: str = '',
    session_id: str | None = None,
    is_refinement: bool = False,
) -> str:
    """Log a query to the daily JSONL file.

    Args:
        query_text: The user's query text.
        query_type: Classification of the query (e.g., "company_lookup", "general").
        result_count: Number of results returned.
        duration_ms: Query duration in milliseconds.
        model_used: LLM model used, if any.
        session_id: Session to associate with. Auto-created if None.
        is_refinement: Whether this is a refinement of a previous query.

    Returns:
        The generated query_id.
    """
    if session_id is None:
        session_id = start_new_session(query_text)

    query_id = f'q_{nanoid_generate()}'
    timestamp = datetime.now(timezone.utc).isoformat()

    entry = {
        'timestamp': timestamp,
        'query_id': query_id,
        'session_id': session_id,
        'query_text': query_text,
        'query_type': query_type,
        'result_count': result_count,
        'duration_ms': duration_ms,
        'model_used': model_used,
        'is_refinement': is_refinement,
    }

    jsonl_file = get_today_file()
    jsonl_file.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(entry) + '\n'

    # Thread-safe and process-safe write with advisory locking
    with open(jsonl_file, 'a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(line)
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

    # Record metric if Phase 3 metrics module is available
    if _record_metric is not None:
        _record_metric(
            'query',
            value=1,
            metadata={
                'query_type': query_type,
                'result_count': result_count,
                'duration_ms': duration_ms,
            },
        )

    _logger.info(
        'Query logged',
        extra={
            'query_id': query_id,
            'query_type': query_type,
            'result_count': result_count,
            'duration_ms': duration_ms,
        },
    )

    return query_id
