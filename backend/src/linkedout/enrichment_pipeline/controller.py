# SPDX-License-Identifier: Apache-2.0
"""Enrichment pipeline controller — trigger enrichment for selected profiles."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Generator, Optional

import requests as http_requests
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from common.controllers.base_controller_utils import create_service_dependency
from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.enrichment_event.entities.enrichment_event_entity import EnrichmentEventEntity
from linkedout.enrichment_pipeline.schemas import EnrichTriggerRequest, EnrichTriggerResponse
from shared.config import get_config
from organization.enrichment_config.entities.enrichment_config_entity import EnrichmentConfigEntity
from shared.infra.db.db_session_manager import DbSessionType, db_session_manager
from shared.utilities.logger import get_logger
from shared.utilities.metrics import record_metric

logger = get_logger(__name__, component="enrichment")

enrichment_pipeline_router = APIRouter(
    prefix='/tenants/{tenant_id}/bus/{bu_id}/enrichment',
    tags=['enrichment-pipeline'],
)

class _EnrichmentTriggerService:
    """Thin service for the enrichment trigger logic — lives with the controller."""

    def __init__(self, session: Session):
        self._session = session

    def trigger_enrichment(
        self,
        tenant_id: str,
        bu_id: str,
        request: EnrichTriggerRequest,
    ) -> EnrichTriggerResponse:
        """Resolve targets, check cache, enqueue enrichment tasks."""
        import time as _time
        _start = _time.time()
        enrichment_cfg = get_config().enrichment

        # Step 1: Resolve target profiles
        target_profiles = self._resolve_targets(request)
        logger.info(
            f'Enrichment batch starting: {len(target_profiles)} targets, '
            f'mode={request.enrichment_mode}, max_count={request.max_count}'
        )

        # Step 2: Apply max_count
        target_profiles = target_profiles[:request.max_count]

        # Step 3: Process each profile — cache check + enqueue
        queued = 0
        cached = 0
        skipped_no_url = 0
        cache_cutoff = datetime.now(timezone.utc) - timedelta(days=enrichment_cfg.cache_ttl_days)

        for profile in target_profiles:
            if not profile.linkedin_url:
                skipped_no_url += 1
                continue

            # Cache check
            if (
                profile.has_enriched_data
                and profile.last_crawled_at is not None
                and profile.last_crawled_at > cache_cutoff
            ):
                # Create cache_hit event
                self._create_enrichment_event(
                    tenant_id, bu_id, request.app_user_id, profile.id,
                    'cache_hit', request.enrichment_mode, 0.0,
                )
                cached += 1
                continue

            # Create queued event
            event = self._create_enrichment_event(
                tenant_id, bu_id, request.app_user_id, profile.id,
                'queued', request.enrichment_mode, enrichment_cfg.cost_per_profile_usd,
            )

            # Run enrichment synchronously with retry
            self._run_enrichment(
                linkedin_url=profile.linkedin_url,
                enrichment_event_id=event.id,
                enrichment_mode=request.enrichment_mode,
                app_user_id=request.app_user_id,
            )
            queued += 1

        self._session.flush()

        _duration_ms = (_time.time() - _start) * 1000
        _cost = round(queued * enrichment_cfg.cost_per_profile_usd, 4)
        logger.info(
            f'Enrichment batch complete: queued={queued}, cached={cached}, '
            f'skipped_no_url={skipped_no_url}, cost_usd={_cost}, '
            f'{_duration_ms:.0f}ms'
        )
        record_metric(
            "enrichment_batch", queued,
            provider="apify", duration_ms=_duration_ms,
            cached=cached, skipped_no_url=skipped_no_url,
            cost_usd=_cost,
        )

        return EnrichTriggerResponse(
            queued=queued,
            cached=cached,
            skipped_no_url=skipped_no_url,
            estimated_cost_usd=_cost,
        )

    def _resolve_targets(self, request: EnrichTriggerRequest) -> list[CrawledProfileEntity]:
        """Resolve profile_ids, connection_ids, all_unenriched into CrawledProfileEntity list."""
        profile_ids: set[str] = set()

        # Direct profile IDs
        if request.profile_ids:
            profile_ids.update(request.profile_ids)

        # Connection IDs → resolve to crawled_profile_ids
        if request.connection_ids:
            connections = self._session.execute(
                select(ConnectionEntity).where(
                    ConnectionEntity.id.in_(request.connection_ids)
                )
            ).scalars().all()
            for conn in connections:
                profile_ids.add(conn.crawled_profile_id)

        # All unenriched
        if request.all_unenriched:
            unenriched = self._session.execute(
                select(CrawledProfileEntity).where(
                    CrawledProfileEntity.has_enriched_data == False,  # noqa: E712
                    CrawledProfileEntity.linkedin_url.isnot(None),
                )
            ).scalars().all()
            profile_ids.update(p.id for p in unenriched)

        if not profile_ids:
            return []

        # Load all target profiles
        profiles = self._session.execute(
            select(CrawledProfileEntity).where(
                CrawledProfileEntity.id.in_(profile_ids)
            )
        ).scalars().all()
        return list(profiles)

    def _create_enrichment_event(
        self,
        tenant_id: str,
        bu_id: str,
        app_user_id: str,
        crawled_profile_id: str,
        event_type: str,
        enrichment_mode: str,
        cost: float,
    ) -> EnrichmentEventEntity:
        event = EnrichmentEventEntity(
            tenant_id=tenant_id,
            bu_id=bu_id,
            app_user_id=app_user_id,
            crawled_profile_id=crawled_profile_id,
            event_type=event_type,
            enrichment_mode=enrichment_mode,
            cost_estimate_usd=cost,
        )
        self._session.add(event)
        self._session.flush()
        return event

    def _run_enrichment(
        self,
        linkedin_url: str,
        enrichment_event_id: str,
        enrichment_mode: str,
        app_user_id: str,
    ) -> None:
        """Run enrichment synchronously with simple retry (3 attempts, exponential backoff)."""
        import time
        from linkedout.enrichment_pipeline.apify_client import (
            LinkedOutApifyClient,
            get_byok_apify_key,
            get_platform_apify_key,
        )
        from linkedout.enrichment_pipeline.post_enrichment import PostEnrichmentService
        from utilities.llm_manager.embedding_factory import get_embedding_provider

        max_attempts = 3
        backoff_seconds = [1, 2, 4]

        for attempt in range(max_attempts):
            try:
                # 1. Get API key
                if enrichment_mode == 'byok':
                    api_key = get_byok_apify_key(app_user_id, self._session)
                else:
                    api_key = get_platform_apify_key()

                # 2. Call Apify
                client = LinkedOutApifyClient(api_key)
                result = client.enrich_profile_sync(linkedin_url)
                if not result:
                    logger.error(f'Apify returned no data for {linkedin_url}')
                    event = self._session.execute(
                        select(EnrichmentEventEntity).where(
                            EnrichmentEventEntity.id == enrichment_event_id
                        )
                    ).scalar_one_or_none()
                    if event:
                        event.event_type = 'failed'
                    self._session.flush()
                    return

                # 3. Delegate to PostEnrichmentService
                embedding_provider = get_embedding_provider()
                service = PostEnrichmentService(self._session, embedding_provider)
                service.process_enrichment_result(result, enrichment_event_id, linkedin_url)
                return

            except Exception:
                if attempt < max_attempts - 1:
                    logger.warning(
                        f'Enrichment attempt {attempt + 1}/{max_attempts} failed for {linkedin_url}, '
                        f'retrying in {backoff_seconds[attempt]}s',
                        exc_info=True,
                    )
                    time.sleep(backoff_seconds[attempt])
                else:
                    logger.error(
                        f'Enrichment failed after {max_attempts} attempts for {linkedin_url}',
                        exc_info=True,
                    )
                    # Mark event as failed on final failure
                    try:
                        event = self._session.execute(
                            select(EnrichmentEventEntity).where(
                                EnrichmentEventEntity.id == enrichment_event_id
                            )
                        ).scalar_one_or_none()
                        if event:
                            event.event_type = 'failed'
                        self._session.flush()
                    except Exception:
                        logger.error(f'Failed to update enrichment event {enrichment_event_id}', exc_info=True)


@enrichment_pipeline_router.post(
    '/enrich',
    summary='Trigger enrichment for selected profiles',
    response_model=EnrichTriggerResponse,
)
def trigger_enrichment(
    tenant_id: str,
    bu_id: str,
    request: EnrichTriggerRequest,
) -> EnrichTriggerResponse:
    """Trigger enrichment for selected profiles, connections, or all unenriched."""
    with db_session_manager.get_session(DbSessionType.WRITE, app_user_id=request.app_user_id) as session:
        service = _EnrichmentTriggerService(session)
        return service.trigger_enrichment(tenant_id, bu_id, request)


# ---------------------------------------------------------------------------
# BYOK Key Management
# ---------------------------------------------------------------------------

class _SetApifyKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=1, description='Apify API key to validate and store')


class _SetApifyKeyResponse(BaseModel):
    status: str
    key_hint: str


class _GetEnrichmentConfigResponse(BaseModel):
    enrichment_mode: str
    key_hint: Optional[str] = None


class _ByokKeyService:
    """Manages BYOK key validation, encryption, and storage."""

    def __init__(self, session: Session):
        self._session = session

    def _get_or_create_config(self, app_user_id: str) -> EnrichmentConfigEntity:
        config = self._session.query(EnrichmentConfigEntity).filter_by(
            app_user_id=app_user_id,
        ).one_or_none()
        if not config:
            config = EnrichmentConfigEntity(app_user_id=app_user_id, enrichment_mode='platform')
            self._session.add(config)
            self._session.flush()
        return config

    def set_key(self, app_user_id: str, api_key: str) -> _SetApifyKeyResponse:
        # Validate key against Apify
        enrichment_cfg = get_config().enrichment
        resp = http_requests.get(
            f'{enrichment_cfg.apify_base_url}/users/me',
            params={'token': api_key},
            timeout=enrichment_cfg.key_validation_timeout_seconds,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail='Invalid Apify API key')

        # Encrypt
        encryption_key = os.environ['TENANT_SECRET_ENCRYPTION_KEY']
        fernet = Fernet(encryption_key.encode())
        encrypted = fernet.encrypt(api_key.encode()).decode()
        hint = f'...{api_key[-4:]}'

        config = self._get_or_create_config(app_user_id)
        config.apify_key_encrypted = encrypted
        config.apify_key_hint = hint
        config.enrichment_mode = 'byok'
        self._session.flush()

        return _SetApifyKeyResponse(status='validated', key_hint=hint)

    def delete_key(self, app_user_id: str) -> None:
        config = self._session.query(EnrichmentConfigEntity).filter_by(
            app_user_id=app_user_id,
        ).one_or_none()
        if not config:
            raise HTTPException(status_code=404, detail='No enrichment config found')
        config.apify_key_encrypted = None
        config.apify_key_hint = None
        config.enrichment_mode = 'platform'
        self._session.flush()

    def get_config(self, app_user_id: str) -> _GetEnrichmentConfigResponse:
        config = self._session.query(EnrichmentConfigEntity).filter_by(
            app_user_id=app_user_id,
        ).one_or_none()
        if not config:
            return _GetEnrichmentConfigResponse(enrichment_mode='platform', key_hint=None)
        return _GetEnrichmentConfigResponse(
            enrichment_mode=config.enrichment_mode,
            key_hint=config.apify_key_hint,
        )


def _get_byok_service() -> Generator[_ByokKeyService, None, None]:
    yield from create_service_dependency(_ByokKeyService, DbSessionType.WRITE)


def _get_byok_read_service() -> Generator[_ByokKeyService, None, None]:
    yield from create_service_dependency(_ByokKeyService, DbSessionType.READ)


@enrichment_pipeline_router.put(
    '/apify-key',
    summary='Set and validate a BYOK Apify API key',
    response_model=_SetApifyKeyResponse,
)
def set_apify_key(
    tenant_id: str,
    bu_id: str,
    request: _SetApifyKeyRequest,
    app_user_id: str = '',
    service: _ByokKeyService = Depends(_get_byok_service),
) -> _SetApifyKeyResponse:
    return service.set_key(app_user_id, request.api_key)


@enrichment_pipeline_router.delete(
    '/apify-key',
    status_code=204,
    summary='Delete the BYOK Apify API key',
)
def delete_apify_key(
    tenant_id: str,
    bu_id: str,
    app_user_id: str = '',
    service: _ByokKeyService = Depends(_get_byok_service),
):
    service.delete_key(app_user_id)


@enrichment_pipeline_router.get(
    '/config',
    summary='Get enrichment configuration (mode + key hint)',
    response_model=_GetEnrichmentConfigResponse,
)
def get_enrichment_config(
    tenant_id: str,
    bu_id: str,
    app_user_id: str = '',
    service: _ByokKeyService = Depends(_get_byok_read_service),
) -> _GetEnrichmentConfigResponse:
    return service.get_config(app_user_id)


# ---------------------------------------------------------------------------
# Enrichment Stats
# ---------------------------------------------------------------------------

class _EnrichmentStatsResponse(BaseModel):
    total_enrichments: int = 0
    cache_hits: int = 0
    cache_hit_rate: float = 0.0
    total_cost_usd: float = 0.0
    saved_via_cache_usd: float = 0.0
    profiles_enriched: int = 0
    profiles_pending: int = 0
    profiles_failed: int = 0
    period: str = 'last_30_days'


class _EnrichmentStatsService:
    """Aggregate enrichment stats from enrichment_event table."""

    def __init__(self, session: Session):
        self._session = session

    def get_stats(self, tenant_id: str, bu_id: str) -> _EnrichmentStatsResponse:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        # Base query for last 30 days, scoped to tenant+bu
        base = (
            self._session.query(EnrichmentEventEntity)
            .filter(
                EnrichmentEventEntity.tenant_id == tenant_id,
                EnrichmentEventEntity.bu_id == bu_id,
                EnrichmentEventEntity.created_at >= cutoff,
            )
        )

        total = base.count()

        # Count by event_type
        type_counts: dict[str, int] = {
            event_type: count
            for event_type, count in self._session.query(
                EnrichmentEventEntity.event_type,
                func.count(EnrichmentEventEntity.id),
            )
            .filter(
                EnrichmentEventEntity.tenant_id == tenant_id,
                EnrichmentEventEntity.bu_id == bu_id,
                EnrichmentEventEntity.created_at >= cutoff,
            )
            .group_by(EnrichmentEventEntity.event_type)
            .all()
        }

        cache_hits = type_counts.get('cache_hit', 0)
        enriched = type_counts.get('crawled', 0) + type_counts.get('completed', 0)
        pending = type_counts.get('queued', 0)
        failed = type_counts.get('failed', 0)

        # Total cost
        cost_result = (
            self._session.query(func.coalesce(func.sum(EnrichmentEventEntity.cost_estimate_usd), 0.0))
            .filter(
                EnrichmentEventEntity.tenant_id == tenant_id,
                EnrichmentEventEntity.bu_id == bu_id,
                EnrichmentEventEntity.created_at >= cutoff,
            )
            .scalar()
        )
        total_cost = float(cost_result)
        saved_via_cache = round(cache_hits * get_config().enrichment.cost_per_profile_usd, 4)

        return _EnrichmentStatsResponse(
            total_enrichments=total,
            cache_hits=cache_hits,
            cache_hit_rate=round(cache_hits / total, 2) if total > 0 else 0.0,
            total_cost_usd=round(total_cost, 4),
            saved_via_cache_usd=saved_via_cache,
            profiles_enriched=enriched,
            profiles_pending=pending,
            profiles_failed=failed,
            period='last_30_days',
        )


def _get_stats_service() -> Generator[_EnrichmentStatsService, None, None]:
    yield from create_service_dependency(_EnrichmentStatsService, DbSessionType.READ)


@enrichment_pipeline_router.get(
    '/stats',
    summary='Get enrichment statistics for the last 30 days',
    response_model=_EnrichmentStatsResponse,
)
def get_enrichment_stats(
    tenant_id: str,
    bu_id: str,
    service: _EnrichmentStatsService = Depends(_get_stats_service),
) -> _EnrichmentStatsResponse:
    return service.get_stats(tenant_id, bu_id)
