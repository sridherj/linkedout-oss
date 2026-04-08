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
from typing import Literal

from sqlalchemy import func, text
from sqlalchemy.orm import Session


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


def check_db_connection() -> HealthCheckResult:
    """Test PostgreSQL connectivity.

    Returns ``pass`` when a simple ``SELECT 1`` succeeds, ``fail`` on any
    connection or query error.
    """
    try:
        from shared.config import get_config

        settings = get_config()
        if not settings.database_url:
            return HealthCheckResult(
                check='db_connection', status='fail', detail='not configured',
            )

        from shared.infra.db.db_session_manager import DbSessionManager, DbSessionType

        db_mgr = DbSessionManager()
        with db_mgr.get_session(DbSessionType.READ) as session:
            session.execute(text('SELECT 1'))
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


def get_db_stats(session: Session | None = None) -> dict:
    """Return database statistics for diagnostics.

    Args:
        session: An existing SQLAlchemy session. When *None*, one is
            created internally via ``DbSessionManager``.

    Returns:
        A dict with keys: ``profiles_total``, ``profiles_with_embeddings``,
        ``profiles_without_embeddings``, ``companies_total``,
        ``connections_total``, ``last_enrichment``, ``schema_version``.
    """
    stats: dict = {
        'profiles_total': 0,
        'profiles_with_embeddings': 0,
        'profiles_without_embeddings': 0,
        'companies_total': 0,
        'connections_total': 0,
        'last_enrichment': None,
        'schema_version': None,
    }

    def _collect(db: Session) -> dict:
        from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
        from linkedout.company.entities.company_entity import CompanyEntity
        from linkedout.connection.entities.connection_entity import ConnectionEntity
        from linkedout.enrichment_event.entities.enrichment_event_entity import EnrichmentEventEntity

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

        # Company count
        stats['companies_total'] = db.execute(
            func.count(CompanyEntity.id).select(),
        ).scalar() or 0

        # Connection count
        stats['connections_total'] = db.execute(
            func.count(ConnectionEntity.id).select(),
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
        from shared.infra.db.db_session_manager import DbSessionManager, DbSessionType

        db_mgr = DbSessionManager()
        with db_mgr.get_session(DbSessionType.READ) as db:
            return _collect(db)
    except Exception:
        return stats
