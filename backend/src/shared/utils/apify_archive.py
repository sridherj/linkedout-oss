# SPDX-License-Identifier: Apache-2.0
"""Append-only JSONL archive for raw Apify responses.

Ensures crawled data survives database loss. Each enrichment appends one
JSON line to ``{data_dir}/crawled/apify-responses.jsonl``.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="enrichment")

ARCHIVE_FILENAME = 'apify-responses.jsonl'


def append_apify_archive(
    linkedin_url: str,
    apify_data: dict,
    source: str,
    data_dir: str | Path | None = None,
) -> None:
    """Append a raw Apify response to the JSONL archive.

    Fire-and-forget: failures are logged but never raised.

    Args:
        linkedin_url: The LinkedIn URL that was enriched.
        apify_data: The raw Apify response dict (written verbatim).
        source: Which flow triggered this (e.g. ``api_enrichment``, ``setup_enrichment``).
        data_dir: Override data directory. If None, resolved from settings.
    """
    try:
        if data_dir is None:
            from shared.config import get_config
            data_dir = get_config().data_dir

        archive_dir = Path(data_dir).expanduser() / 'crawled'
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / ARCHIVE_FILENAME

        line = json.dumps({
            'archived_at': datetime.now(timezone.utc).isoformat(),
            'linkedin_url': linkedin_url,
            'source': source,
            'data': apify_data,
        }, ensure_ascii=False, default=str)

        with open(archive_path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

    except Exception:
        logger.warning('Failed to archive Apify response for %s', linkedin_url, exc_info=True)
