# SPDX-License-Identifier: Apache-2.0
"""Apify LinkedIn profile enrichment client with key rotation and BYOK support.

Supports multiple API keys for round-robin rotation to spread rate limits
across Apify accounts. Configure via settings:
  - Single key:   APIFY_API_KEY=apify_api_...
  - Multiple keys: APIFY_API_KEYS=key1,key2,key3  (comma-separated)
  - Or as a YAML list in secrets.yaml under apify_api_keys.
"""
import os
import time
from typing import Optional

import requests
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from organization.enrichment_config.entities.enrichment_config_entity import EnrichmentConfigEntity
from shared.config import get_config
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="enrichment")

# This Actor ID is coupled to the response schema we parse.
# Changing it will break enrichment result parsing.
# See: https://apify.com/capademir/linkedin-profile-scraper
APIFY_LINKEDIN_ACTOR_ID = 'LpVuK3Zozwuipa5bp'

# Scraper mode is tied to Actor behavior — not user-configurable.
ACTOR_SCRAPER_MODE = 'Profile details no email ($4 per 1k)'

# ---------------------------------------------------------------------------
# Apify error hierarchy
# ---------------------------------------------------------------------------

class ApifyError(Exception):
    """Base class for Apify-specific errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ApifyCreditExhaustedError(ApifyError):
    """HTTP 402 — account has no credits remaining."""


class ApifyRateLimitError(ApifyError):
    """HTTP 429 — rate limit hit, retry after backoff."""


class ApifyAuthError(ApifyError):
    """HTTP 401/403 — invalid or revoked API key."""


class ApifyInvalidUrlError(ApifyError):
    """URL is not a valid LinkedIn profile URL — must not be sent to Apify."""


class AllKeysExhaustedError(ApifyError):
    """All configured Apify keys are exhausted or invalid."""


# ---------------------------------------------------------------------------
# Per-key health tracking
# ---------------------------------------------------------------------------

class KeyHealthTracker:
    """Tracks which Apify keys are healthy, exhausted, or rate-limited."""

    def __init__(self, keys: list[str]):
        self._keys = keys
        self._exhausted: set[int] = set()   # indices of 402'd keys
        self._invalid: set[int] = set()     # indices of 401/403'd keys
        self._current = 0

    def next_key(self) -> str:
        """Return the next healthy key, or raise AllKeysExhaustedError."""
        total = len(self._keys)
        checked = 0
        while checked < total:
            idx = self._current % total
            self._current += 1
            if idx not in self._exhausted and idx not in self._invalid:
                return self._keys[idx]
            checked += 1
        raise AllKeysExhaustedError("All Apify keys are exhausted or invalid")

    def mark_exhausted(self, key: str) -> None:
        idx = self._keys.index(key)
        self._exhausted.add(idx)

    def mark_invalid(self, key: str) -> None:
        idx = self._keys.index(key)
        self._invalid.add(idx)

    def healthy_count(self) -> int:
        return len(self._keys) - len(self._exhausted) - len(self._invalid)

    def summary(self) -> str:
        """Human-readable status of all keys for error reporting."""
        lines = []
        for i, key in enumerate(self._keys):
            hint = f"…{key[-4:]}"
            if i in self._exhausted:
                lines.append(f"  Key {i+1} ({hint}): credits exhausted (HTTP 402)")
            elif i in self._invalid:
                lines.append(f"  Key {i+1} ({hint}): invalid or revoked (HTTP 401/403)")
            else:
                lines.append(f"  Key {i+1} ({hint}): healthy")
        return "\n".join(lines)


# Module-level key tracker for true round-robin across calls
_key_tracker: KeyHealthTracker | None = None


def get_platform_apify_key() -> str:
    """Round-robin across configured Apify API keys, skipping exhausted/invalid ones."""
    global _key_tracker
    if _key_tracker is None:
        cfg = get_config()
        keys = cfg.get_apify_api_keys()
        if keys:
            logger.info(f'Apify key rotation: {len(keys)} keys loaded')
        elif cfg.apify_api_key:
            keys = [cfg.apify_api_key]
        else:
            raise ValueError(
                'APIFY_API_KEY is not configured.\n'
                'Set APIFY_API_KEY for a single key, or APIFY_API_KEYS=key1,key2,key3 '
                'for round-robin rotation.\n'
                'Configure in secrets.yaml, .env, or environment variables.'
            )
        _key_tracker = KeyHealthTracker(keys)
    return _key_tracker.next_key()


def get_key_tracker() -> KeyHealthTracker | None:
    """Return the current key tracker (for CLI health status reporting)."""
    return _key_tracker


def reset_key_cycle() -> None:
    """Reset key tracker — useful for testing."""
    global _key_tracker
    _key_tracker = None


def get_byok_apify_key(app_user_id: str, db_session: Session) -> str:
    """Decrypt BYOK key from enrichment_config."""
    config = db_session.query(EnrichmentConfigEntity).filter_by(
        app_user_id=app_user_id
    ).first()
    if not config or not config.apify_key_encrypted:
        raise ValueError('No BYOK key configured for this user')
    encryption_key = os.environ['TENANT_SECRET_ENCRYPTION_KEY']
    fernet = Fernet(encryption_key.encode())
    return fernet.decrypt(config.apify_key_encrypted.encode()).decode()


def _validate_linkedin_url(url: str) -> None:
    """Raise ApifyInvalidUrlError if *url* is not a LinkedIn profile URL."""
    from shared.utils.linkedin_url import normalize_linkedin_url

    if normalize_linkedin_url(url) is None:
        raise ApifyInvalidUrlError(
            f"Not a LinkedIn URL — refusing to send to Apify: {url}"
        )


class LinkedOutApifyClient:
    """Client for Apify LinkedIn profile scraper actor."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.actor_id = APIFY_LINKEDIN_ACTOR_ID
        cfg = get_config().enrichment
        self.base_url = cfg.apify_base_url
        self._cfg = cfg

    def _build_input(self, linkedin_urls: list[str]) -> dict:
        return {
            'profileScraperMode': ACTOR_SCRAPER_MODE,
            'queries': linkedin_urls,
        }

    def enrich_profile_sync(self, linkedin_url: str) -> Optional[dict]:
        """Synchronous single-profile enrichment. Returns raw Apify response or None."""
        _validate_linkedin_url(linkedin_url)
        url = f'{self.base_url}/acts/{self.actor_id}/run-sync-get-dataset-items'
        resp = requests.post(
            url,
            params={'token': self.api_key},
            json=self._build_input([linkedin_url]),
            timeout=self._cfg.sync_timeout_seconds,
        )
        if not resp.ok:
            logger.error(f'Apify sync call failed: {resp.status_code} {resp.text[:200]}')
            if resp.status_code == 402:
                raise ApifyCreditExhaustedError(
                    f'Apify credits exhausted (HTTP 402)', status_code=402
                )
            elif resp.status_code == 429:
                raise ApifyRateLimitError(
                    f'Apify rate limit hit (HTTP 429)', status_code=429
                )
            elif resp.status_code in (401, 403):
                raise ApifyAuthError(
                    f'Apify authentication failed (HTTP {resp.status_code})',
                    status_code=resp.status_code,
                )
            else:
                raise ApifyError(
                    f'Apify call failed: HTTP {resp.status_code}',
                    status_code=resp.status_code,
                )
        items = resp.json()
        if items and len(items) > 0:
            return items[0]
        return None

    def enrich_profiles_async(self, linkedin_urls: list[str]) -> str:
        """Start async run for multiple profiles. Returns run_id."""
        for u in linkedin_urls:
            _validate_linkedin_url(u)
        url = f'{self.base_url}/acts/{self.actor_id}/runs'
        resp = requests.post(
            url,
            params={'token': self.api_key},
            json=self._build_input(linkedin_urls),
            timeout=self._cfg.async_start_timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()['data']['id']

    def poll_run(self, run_id: str, timeout: int | None = None, poll_interval: int | None = None) -> str:
        """Poll until run completes. Returns dataset_id."""
        if timeout is None:
            timeout = self._cfg.run_poll_timeout_seconds
        if poll_interval is None:
            poll_interval = self._cfg.run_poll_interval_seconds
        url = f'{self.base_url}/actor-runs/{run_id}'
        elapsed = 0
        while elapsed < timeout:
            resp = requests.get(url, params={'token': self.api_key}, timeout=15)
            resp.raise_for_status()
            data = resp.json()['data']
            status = data['status']
            if status == 'SUCCEEDED':
                return data['defaultDatasetId']
            if status in ('FAILED', 'ABORTED', 'TIMED-OUT'):
                raise RuntimeError(f'Apify run {run_id} ended with status: {status}')
            time.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(f'Apify run {run_id} did not complete within {timeout}s')

    def poll_run_safe(self, run_id: str, timeout: int | None = None, poll_interval: int | None = None) -> tuple[str, str]:
        """Poll until run reaches a terminal state. Returns (status, dataset_id).

        Unlike poll_run(), this method does NOT raise on FAILED/ABORTED/TIMED-OUT.
        It always returns the dataset_id (which Apify allocates at run creation,
        regardless of outcome) so the caller can fetch partial results.

        Returns:
            Tuple of (status, dataset_id) where status is one of:
            SUCCEEDED, FAILED, ABORTED, TIMED-OUT

        Raises:
            TimeoutError: If the run does not reach a terminal state within timeout.
        """
        if timeout is None:
            timeout = self._cfg.run_poll_timeout_seconds
        if poll_interval is None:
            poll_interval = self._cfg.run_poll_interval_seconds
        url = f'{self.base_url}/actor-runs/{run_id}'
        elapsed = 0
        while elapsed < timeout:
            resp = requests.get(url, params={'token': self.api_key}, timeout=15)
            resp.raise_for_status()
            data = resp.json()['data']
            status = data['status']
            if status in ('SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT'):
                return (status, data['defaultDatasetId'])
            time.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(f'Apify run {run_id} did not complete within {timeout}s')

    def check_run_status(self, run_id: str) -> tuple[str, str] | None:
        """Single non-blocking status check. Returns (status, dataset_id) if terminal, None if still running."""
        url = f'{self.base_url}/actor-runs/{run_id}'
        resp = requests.get(url, params={'token': self.api_key}, timeout=15)
        resp.raise_for_status()
        data = resp.json()['data']
        status = data['status']
        if status in ('SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT'):
            return (status, data['defaultDatasetId'])
        return None

    def fetch_results(self, dataset_id: str) -> list[dict]:
        """Fetch results from a completed dataset."""
        url = f'{self.base_url}/datasets/{dataset_id}/items'
        resp = requests.get(url, params={'token': self.api_key}, timeout=self._cfg.fetch_results_timeout_seconds)
        resp.raise_for_status()
        return resp.json()
