# SPDX-License-Identifier: Apache-2.0
"""Download profile pictures from Apify profilePicture URLs.

Queries crawled_profile rows with raw_profile containing a profilePicture URL,
downloads the 800x800 image to a local directory, and updates profile_image_url.

Usage:
    cd src && uv run python -m dev_tools.download_profile_pics [--limit N] [--retry-failed]
"""
import asyncio
import json
import time
from pathlib import Path

import click
import httpx
from sqlalchemy import text

from dev_tools.db.fixed_data import SYSTEM_USER_ID
from shared.config import get_config
from shared.infra.db.cli_db import cli_db_manager
from shared.infra.db.db_session_manager import DbSessionType

IMAGES_DIR = Path(get_config().data_dir) / 'images'
MAX_CONCURRENT = 10
BATCH_DELAY = 0.1  # seconds between batches


def extract_image_url(raw_profile: str) -> str | None:
    """Extract the profilePicture URL from raw_profile JSON."""
    if not raw_profile:
        return None
    try:
        data = json.loads(raw_profile) if isinstance(raw_profile, str) else raw_profile
    except (json.JSONDecodeError, TypeError):
        return None

    pic = data.get('profilePicture')
    if not pic:
        return None

    # Direct URL string
    if isinstance(pic, str):
        return pic if pic.startswith('http') else None

    # Dict with 'url' key
    if isinstance(pic, dict):
        url = pic.get('url', '')
        return url if url.startswith('http') else None

    return None


def get_profiles_to_download(limit: int | None, retry_failed: bool) -> list[tuple[str, str, str]]:
    """Fetch (id, public_identifier, raw_profile) rows needing image download."""
    db_manager = cli_db_manager()
    with db_manager.get_session(DbSessionType.READ, app_user_id=SYSTEM_USER_ID) as session:
        if retry_failed:
            # Re-attempt all profiles that have a profilePicture but no local image
            query = text("""
                SELECT id, public_identifier, raw_profile
                FROM crawled_profile
                WHERE raw_profile IS NOT NULL
                  AND profile_image_url IS NULL
                  AND raw_profile LIKE '%profilePicture%'
            """)
        else:
            query = text("""
                SELECT id, public_identifier, raw_profile
                FROM crawled_profile
                WHERE raw_profile IS NOT NULL
                  AND profile_image_url IS NULL
                  AND raw_profile LIKE '%profilePicture%'
            """)

        if limit:
            query = text(str(query) + f' LIMIT {limit}')

        rows = session.execute(query).fetchall()
        return [(r[0], r[1], r[2]) for r in rows]


async def download_image(
    client: httpx.AsyncClient,
    profile_id: str,
    identifier: str,
    url: str,
    images_dir: Path,
) -> tuple[str, str | None, str | None]:
    """Download a single image. Returns (profile_id, local_path, error)."""
    filename = f'{identifier}.jpg' if identifier else f'{profile_id}.jpg'
    local_path = images_dir / filename

    # Idempotent: skip if already exists
    if local_path.exists():
        return profile_id, str(local_path), None

    try:
        resp = await client.get(url, follow_redirects=True, timeout=30)
        if resp.status_code == 200:
            local_path.write_bytes(resp.content)
            return profile_id, str(local_path), None
        return profile_id, None, f'HTTP {resp.status_code}'
    except Exception as e:
        return profile_id, None, str(e)


async def download_batch(
    profiles: list[tuple[str, str, str]],
    images_dir: Path,
) -> dict[str, int]:
    """Download images for all profiles with concurrency limit."""
    db_manager = cli_db_manager()
    stats = {'attempted': 0, 'success': 0, 'failed': 0, 'skipped_no_url': 0}
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    # Pre-process: extract URLs
    tasks_to_run = []
    for profile_id, identifier, raw_profile in profiles:
        url = extract_image_url(raw_profile)
        if not url:
            stats['skipped_no_url'] += 1
            continue
        tasks_to_run.append((profile_id, identifier, url))

    async with httpx.AsyncClient() as client:
        async def bounded_download(pid, ident, url):
            async with semaphore:
                return await download_image(client, pid, ident, url, images_dir)

        # Process in sub-batches of 100 for DB updates
        for batch_start in range(0, len(tasks_to_run), 100):
            batch = tasks_to_run[batch_start:batch_start + 100]
            coros = [bounded_download(pid, ident, url) for pid, ident, url in batch]
            results = await asyncio.gather(*coros)

            # Update DB with successful downloads
            successes = [(pid, path) for pid, path, _err in results if path]
            failures = [(pid, err) for pid, _path, err in results if err]

            if successes:
                with db_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
                    for pid, path in successes:
                        session.execute(
                            text('UPDATE crawled_profile SET profile_image_url = :url WHERE id = :id'),
                            {'url': path, 'id': pid},
                        )

            stats['attempted'] += len(batch)
            stats['success'] += len(successes)
            stats['failed'] += len(failures)

            if failures and len(failures) <= 5:
                for pid, err in failures:
                    click.echo(f'  FAIL {pid}: {err}', err=True)

            await asyncio.sleep(BATCH_DELAY)

    return stats


@click.command()
@click.option('--limit', default=None, type=int, help='Max profiles to process')
@click.option('--retry-failed', is_flag=True, help='Retry profiles with no image yet')
def main(limit: int | None, retry_failed: bool):
    """Download profile pictures from Apify data."""
    start_time = time.time()

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    click.echo('Fetching profiles needing image download...')
    profiles = get_profiles_to_download(limit, retry_failed)
    click.echo(f'  -> {len(profiles)} profiles to process')

    if not profiles:
        click.echo('Nothing to do.')
        return

    stats = asyncio.run(download_batch(profiles, IMAGES_DIR))

    elapsed = time.time() - start_time
    click.echo('\n=== IMAGE DOWNLOAD COMPLETE ===')
    click.echo(f'Attempted:      {stats["attempted"]:>8,}')
    click.echo(f'Success:        {stats["success"]:>8,}')
    click.echo(f'Failed:         {stats["failed"]:>8,}')
    click.echo(f'No URL in data: {stats["skipped_no_url"]:>8,}')
    click.echo(f'Elapsed:        {elapsed:>7.1f}s')


if __name__ == '__main__':
    main()
