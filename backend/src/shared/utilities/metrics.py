# SPDX-License-Identifier: Apache-2.0
"""File-based metrics collection — append-only JSONL with rolling summary.

Records operational metrics as append-only JSONL files (one per day) and
maintains a rolling summary in summary.json. No external dependencies —
just file I/O.

File layout::

    {metrics_dir}/
        daily/
            2026-04-08.jsonl   # one JSON object per line
            2026-04-09.jsonl
        summary.json           # rolling key-value summary

Each JSONL line has the shape::

    {"ts": "2026-04-08T14:23:05.123456Z", "metric": "profiles_imported", "value": 3847, "source": "csv"}

Usage::

    from shared.utilities.metrics import record_metric, read_summary, update_summary

    record_metric("profiles_imported", 3847, source="csv")
    update_summary({"profiles_total": 12500})
    summary = read_summary()
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _get_metrics_dir() -> Path:
    """Return the metrics directory from env or default.

    Reads ``LINKEDOUT_METRICS_DIR`` from the environment. Falls back to
    ``~/linkedout-data/metrics/`` when the variable is unset.
    """
    metrics_dir = os.environ.get(
        'LINKEDOUT_METRICS_DIR',
        str(Path.home() / 'linkedout-data' / 'metrics'),
    )
    return Path(metrics_dir)


def record_metric(name: str, value: Any, *, metrics_dir: Path | None = None, **context: Any) -> None:
    """Append a metric event to the daily JSONL file.

    Args:
        name: Metric name (e.g., ``"profiles_imported"``).
        value: Metric value (typically a count or duration).
        metrics_dir: Override the metrics directory. Uses
            ``LINKEDOUT_METRICS_DIR`` or the default when *None*.
        **context: Additional context fields written into the JSONL line
            (e.g., ``source="csv"``, ``duration_ms=120``).

    The function is thread-safe on POSIX systems: each call writes a
    single line under ``PIPE_BUF`` (4 096 bytes) in append mode, which
    the kernel guarantees to be atomic.
    """
    base = metrics_dir or _get_metrics_dir()
    daily_dir = base / 'daily'
    daily_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    filepath = daily_dir / f'{today}.jsonl'

    record = {
        'ts': datetime.now(timezone.utc).isoformat(),
        'metric': name,
        'value': value,
        **context,
    }

    line = json.dumps(record, separators=(',', ':')) + '\n'

    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(line)
        f.flush()


def read_summary(metrics_dir: Path | None = None) -> dict:
    """Read the rolling summary from ``summary.json``.

    Args:
        metrics_dir: Override the metrics directory. Uses
            ``LINKEDOUT_METRICS_DIR`` or the default when *None*.

    Returns:
        A dict with keys like ``profiles_total``, ``companies_total``, etc.
        Returns an empty dict if ``summary.json`` doesn't exist.
    """
    base = metrics_dir or _get_metrics_dir()
    summary_path = base / 'summary.json'

    if not summary_path.exists():
        return {}

    with open(summary_path, encoding='utf-8') as f:
        return json.load(f)


def update_summary(updates: dict, *, metrics_dir: Path | None = None) -> dict:
    """Merge *updates* into ``summary.json`` and return the result.

    Reads the existing summary (or starts from ``{}``), merges *updates*
    (overwriting matching keys), and writes the result back atomically.

    Args:
        updates: Key-value pairs to merge into the summary.
        metrics_dir: Override the metrics directory. Uses
            ``LINKEDOUT_METRICS_DIR`` or the default when *None*.

    Returns:
        The merged summary dict after writing.
    """
    base = metrics_dir or _get_metrics_dir()
    base.mkdir(parents=True, exist_ok=True)
    summary_path = base / 'summary.json'

    existing = {}
    if summary_path.exists():
        with open(summary_path, encoding='utf-8') as f:
            existing = json.load(f)

    existing.update(updates)

    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=2)

    return existing
