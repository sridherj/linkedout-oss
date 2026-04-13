# SPDX-License-Identifier: Apache-2.0
"""Reusable health check functions for LinkedOut diagnostics.

Each function returns a ``HealthCheckResult`` (or list thereof) describing
whether a particular subsystem is healthy. Functions handle errors
gracefully — they return ``fail`` status instead of raising exceptions.

Usage::

    from shared.utilities.health_checks import (
        check_api_keys,
        check_db_connection,
        check_disk_space,
        check_embedding_model,
        get_db_stats,
    )

    result = check_db_connection()
    print(result.status)  # "pass" | "fail" | "skip"
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from sqlalchemy import func, text
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from shared.infra.db.db_session_manager import DbSessionManager


@dataclass
class HealthCheckResult:
    """Result of a single health check probe.

    Attributes:
        check: Name of the health check (e.g., ``"db_connection"``).
        status: One of ``"pass"``, ``"fail"``, or ``"skip"``.
        detail: Optional human-readable context.
    """

    check: str
    status: Literal['pass', 'fail', 'skip']
    detail: str = ''


def _get_data_dir() -> Path:
    """Return the LinkedOut data directory from env or default."""
    return Path(
        os.environ.get('LINKEDOUT_DATA_DIR', os.path.expanduser('~/linkedout-data'))
    )


def check_db_connection(
    db_manager: 'DbSessionManager | None' = None,
    session: Session | None = None,
) -> HealthCheckResult:
    """Test PostgreSQL connectivity.

    Args:
        db_manager: An existing ``DbSessionManager``. When *None*, one is
            created internally via ``cli_db_manager()``.
        session: An existing SQLAlchemy session. When provided, uses it
            directly instead of creating one via ``db_manager``.

    Returns ``pass`` when a simple ``SELECT 1`` succeeds, ``fail`` on any
    connection or query error.
    """
    try:
        if session is not None:
            session.execute(text('SELECT 1'))
            return HealthCheckResult(check='db_connection', status='pass')

        if db_manager is None:
            from shared.config import get_config
            settings = get_config()
            if not settings.database_url:
                return HealthCheckResult(
                    check='db_connection', status='fail',
                    detail='Database URL not configured',
                )
            from shared.infra.db.cli_db import cli_db_manager
            db_manager = cli_db_manager()

        from shared.infra.db.db_session_manager import DbSessionType

        with db_manager.get_session(DbSessionType.READ) as sess:
            sess.execute(text('SELECT 1'))
        return HealthCheckResult(check='db_connection', status='pass')
    except Exception as e:
        return HealthCheckResult(
            check='db_connection', status='fail', detail=str(e),
        )


def check_embedding_model() -> HealthCheckResult:
    """Check if the configured embedding model is available.

    Returns ``pass`` when the embedding provider is configured and accessible,
    ``skip`` when no embedding provider is set up.
    """
    try:
        from shared.config import get_config

        settings = get_config()

        if settings.embedding.provider == 'openai':
            if settings.openai_api_key:
                return HealthCheckResult(
                    check='embedding_model',
                    status='pass',
                    detail=f'openai/{settings.embedding.model}',
                )
            return HealthCheckResult(
                check='embedding_model',
                status='skip',
                detail='OpenAI API key not configured',
            )

        if settings.embedding.provider == 'local':
            return HealthCheckResult(
                check='embedding_model',
                status='pass',
                detail=f'local/{settings.embedding.model}',
            )

        return HealthCheckResult(
            check='embedding_model',
            status='skip',
            detail=f'unknown provider: {settings.embedding.provider}',
        )
    except Exception as e:
        return HealthCheckResult(
            check='embedding_model', status='fail', detail=str(e),
        )


def check_api_keys() -> list[HealthCheckResult]:
    """Check configured API keys. NEVER returns actual key values.

    Returns a list of ``HealthCheckResult`` with ``"configured"`` or
    ``"not configured"`` for each tracked key.
    """
    try:
        from shared.config import get_config

        settings = get_config()

        results = []
        for key_name, value in [
            ('openai', settings.openai_api_key),
            ('apify', settings.apify_api_key),
        ]:
            configured = bool(value)
            results.append(
                HealthCheckResult(
                    check=f'api_key_{key_name}',
                    status='pass' if configured else 'skip',
                    detail='configured' if configured else 'not configured',
                ),
            )
        return results
    except Exception as e:
        return [
            HealthCheckResult(check='api_keys', status='fail', detail=str(e)),
        ]


def check_disk_space() -> HealthCheckResult:
    """Check disk space for the linkedout-data directory.

    Returns ``pass`` if more than 1 GB is free on the filesystem
    containing the data directory.
    """
    try:
        data_dir = _get_data_dir()
        # Use the data dir if it exists, otherwise check its parent
        check_path = data_dir if data_dir.exists() else data_dir.parent
        usage = shutil.disk_usage(check_path)
        free_gb = usage.free / (1024 ** 3)

        if free_gb > 1.0:
            return HealthCheckResult(
                check='disk_space',
                status='pass',
                detail=f'{free_gb:.1f} GB free',
            )
        return HealthCheckResult(
            check='disk_space',
            status='fail',
            detail=f'{free_gb:.1f} GB free (< 1 GB)',
        )
    except Exception as e:
        return HealthCheckResult(
            check='disk_space', status='fail', detail=str(e),
        )


def get_db_stats(
    session: Session | None = None,
    db_manager: 'DbSessionManager | None' = None,
) -> dict:
    """Return database statistics for diagnostics.

    Args:
        session: An existing SQLAlchemy session. When *None*, one is
            created internally via ``db_manager`` or ``cli_db_manager()``.
        db_manager: An existing ``DbSessionManager``. Used when *session*
            is None. When both are *None*, ``cli_db_manager()`` is called.

    Returns:
        A dict with keys: ``profiles_total``, ``profiles_enrichable``,
        ``profiles_with_embeddings``, ``profiles_without_embeddings``,
        ``companies_total``, ``connections_total``, ``last_enrichment``,
        ``schema_version``.
    """
    stats: dict = {
        'profiles_total': 0,
        'profiles_with_embeddings': 0,
        'profiles_without_embeddings': 0,
        'companies_total': 0,
        'connections_total': 0,
        'last_enrichment': None,
        'schema_version': None,
        # Enrichment
        'profiles_enrichable': 0,
        'profiles_enriched': 0,
        'profiles_unenriched': 0,
        'enrichment_events_total': 0,
        # Affinity
        'connections_with_affinity': 0,
        'connections_without_affinity': 0,
        # Owner profile
        'owner_profile_exists': False,
        # System records
        'system_tenant_exists': False,
        'system_bu_exists': False,
        'system_user_exists': False,
        # Seed data
        'seed_companies_loaded': 0,
        'funding_rounds_total': 0,
    }

    def _collect(db: Session) -> dict:
        from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
        from linkedout.company.entities.company_entity import CompanyEntity
        from linkedout.connection.entities.connection_entity import ConnectionEntity
        from linkedout.enrichment_event.entities.enrichment_event_entity import EnrichmentEventEntity
        from organization.entities.tenant_entity import TenantEntity
        from organization.entities.bu_entity import BuEntity
        from organization.entities.app_user_entity import AppUserEntity
        from linkedout.funding.entities.funding_round_entity import FundingRoundEntity

        # Profile counts
        total = db.execute(
            func.count(CrawledProfileEntity.id).select(),
        ).scalar() or 0

        with_embeddings = db.execute(
            func.count(CrawledProfileEntity.id).select().where(
                CrawledProfileEntity.embedding_openai.isnot(None)
                | CrawledProfileEntity.embedding_nomic.isnot(None),
            ),
        ).scalar() or 0

        stats['profiles_total'] = total
        stats['profiles_with_embeddings'] = with_embeddings
        stats['profiles_without_embeddings'] = total - with_embeddings

        # Enrichment counts — only profiles with valid LinkedIn /in/ URLs are enrichable
        enrichable = db.execute(
            func.count(CrawledProfileEntity.id).select().where(
                CrawledProfileEntity.linkedin_url.like('https://www.linkedin.com/in/%'),
            ),
        ).scalar() or 0
        enriched = db.execute(
            func.count(CrawledProfileEntity.id).select().where(
                CrawledProfileEntity.has_enriched_data.is_(True),
            ),
        ).scalar() or 0
        stats['profiles_enrichable'] = enrichable
        stats['profiles_enriched'] = enriched
        stats['profiles_unenriched'] = enrichable - enriched

        stats['enrichment_events_total'] = db.execute(
            func.count(EnrichmentEventEntity.id).select(),
        ).scalar() or 0

        # Company count
        stats['companies_total'] = db.execute(
            func.count(CompanyEntity.id).select(),
        ).scalar() or 0

        # Connection counts
        conn_total = db.execute(
            func.count(ConnectionEntity.id).select(),
        ).scalar() or 0
        stats['connections_total'] = conn_total

        with_affinity = db.execute(
            func.count(ConnectionEntity.id).select().where(
                ConnectionEntity.affinity_score.isnot(None),
            ),
        ).scalar() or 0
        stats['connections_with_affinity'] = with_affinity
        stats['connections_without_affinity'] = conn_total - with_affinity

        # Owner profile
        owner_count = db.execute(
            func.count(CrawledProfileEntity.id).select().where(
                CrawledProfileEntity.data_source == 'setup',
            ),
        ).scalar() or 0
        stats['owner_profile_exists'] = owner_count > 0

        # System records
        stats['system_tenant_exists'] = (db.execute(
            func.count(TenantEntity.id).select().where(
                TenantEntity.id == 'tenant_sys_001',
            ),
        ).scalar() or 0) > 0

        stats['system_bu_exists'] = (db.execute(
            func.count(BuEntity.id).select().where(
                BuEntity.id == 'bu_sys_001',
            ),
        ).scalar() or 0) > 0

        stats['system_user_exists'] = (db.execute(
            func.count(AppUserEntity.id).select().where(
                AppUserEntity.id == 'usr_sys_001',
            ),
        ).scalar() or 0) > 0

        # Seed data
        stats['seed_companies_loaded'] = stats['companies_total']

        stats['funding_rounds_total'] = db.execute(
            func.count(FundingRoundEntity.id).select(),
        ).scalar() or 0

        # Last enrichment date
        last_enrichment = db.execute(
            func.max(EnrichmentEventEntity.created_at).select(),
        ).scalar()
        if last_enrichment:
            stats['last_enrichment'] = last_enrichment.isoformat()

        # Schema version (Alembic)
        try:
            row = db.execute(text('SELECT version_num FROM alembic_version LIMIT 1')).first()
            if row:
                stats['schema_version'] = row[0]
        except Exception:
            stats['schema_version'] = None

        return stats

    if session is not None:
        return _collect(session)

    try:
        if db_manager is None:
            from shared.infra.db.cli_db import cli_db_manager
            db_manager = cli_db_manager()

        from shared.infra.db.db_session_manager import DbSessionType

        with db_manager.get_session(DbSessionType.READ) as db:
            return _collect(db)
    except Exception:
        return stats


def compute_issues(db_stats: dict, health_checks: list[dict]) -> list[dict]:
    """Derive actionable issues from raw diagnostics data."""
    issues = []

    # System records
    if not db_stats.get('system_tenant_exists'):
        issues.append({
            'severity': 'CRITICAL', 'category': 'bootstrap',
            'message': 'System tenant record missing — CSV import and enrichment will fail',
            'action': 'linkedout setup --demo  # or --full',
        })

    # Owner profile
    if not db_stats.get('owner_profile_exists') and db_stats.get('profiles_total', 0) > 0:
        issues.append({
            'severity': 'WARNING', 'category': 'setup',
            'message': 'Owner profile not configured — affinity scoring needs your profile as baseline',
            'action': 'Run /linkedout-setup and provide your LinkedIn URL',
        })

    # Embeddings
    without_emb = db_stats.get('profiles_without_embeddings', 0)
    if without_emb > 0:
        issues.append({
            'severity': 'WARNING', 'category': 'embeddings',
            'message': f'{without_emb:,} profiles without embeddings — semantic search won\'t find them',
            'action': 'linkedout embed',
        })

    # Enrichment
    unenriched = db_stats.get('profiles_unenriched', 0)
    if unenriched > 0:
        issues.append({
            'severity': 'INFO', 'category': 'enrichment',
            'message': f'{unenriched:,} profiles not enriched — only name/company/title available',
            'action': 'linkedout enrich  # requires Apify key',
        })

    # Affinity
    without_affinity = db_stats.get('connections_without_affinity', 0)
    if without_affinity > 0:
        issues.append({
            'severity': 'INFO', 'category': 'affinity',
            'message': f'{without_affinity:,} connections without affinity scores',
            'action': 'linkedout compute-affinity',
        })

    # Health check failures
    for check in health_checks:
        if check['status'] == 'fail':
            issues.append({
                'severity': 'CRITICAL', 'category': check['check'],
                'message': check.get('detail', f'{check["check"]} failed'),
                'action': 'linkedout diagnostics --repair',
            })

    return issues
