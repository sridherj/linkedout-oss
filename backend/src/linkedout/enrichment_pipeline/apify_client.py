# SPDX-License-Identifier: Apache-2.0
"""Apify LinkedIn profile enrichment client with key rotation and BYOK support.

Supports multiple API keys for round-robin rotation to spread rate limits
across Apify accounts. Configure via settings:
  - Single key:   APIFY_API_KEY=apify_api_...
  - Multiple keys: APIFY_API_KEYS=key1,key2,key3  (comma-separated)
  - Or as a YAML list in secrets.yaml under apify_api_keys.
"""
import itertools
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

# Module-level key cycle for true round-robin across calls
_key_cycle = None


def get_platform_apify_key() -> str:
    """Round-robin across configured Apify API keys.

    Key resolution order:
      1. apify_api_keys list (round-robin if multiple)
      2. apify_api_key (single key fallback)
    """
    global _key_cycle
    if _key_cycle is None:
        cfg = get_config()
        keys = cfg.get_apify_api_keys()
        if keys:
            logger.info(f'Apify key rotation: {len(keys)} keys loaded')
            _key_cycle = itertools.cycle(keys)
        elif cfg.apify_api_key:
            _key_cycle = itertools.cycle([cfg.apify_api_key])
        else:
            raise ValueError(
                'APIFY_API_KEY is not configured.\n'
                'Set APIFY_API_KEY for a single key, or APIFY_API_KEYS=key1,key2,key3 '
                'for round-robin rotation.\n'
                'Configure in secrets.yaml, .env, or environment variables.'
            )
    return next(_key_cycle)


def reset_key_cycle() -> None:
    """Reset key cycle — useful for testing."""
    global _key_cycle
    _key_cycle = None


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
        url = f'{self.base_url}/acts/{self.actor_id}/run-sync-get-dataset-items'
        resp = requests.post(
            url,
            params={'token': self.api_key},
            json=self._build_input([linkedin_url]),
            timeout=self._cfg.sync_timeout_seconds,
        )
        if not resp.ok:
            logger.error(f'Apify sync call failed: {resp.status_code} {resp.text[:200]}')
            return None
        items = resp.json()
        if items and len(items) > 0:
            return items[0]
        return None

    def enrich_profiles_async(self, linkedin_urls: list[str]) -> str:
        """Start async run for multiple profiles. Returns run_id."""
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

    def fetch_results(self, dataset_id: str) -> list[dict]:
        """Fetch results from a completed dataset."""
        url = f'{self.base_url}/datasets/{dataset_id}/items'
        resp = requests.get(url, params={'token': self.api_key}, timeout=self._cfg.fetch_results_timeout_seconds)
        resp.raise_for_status()
        return resp.json()
