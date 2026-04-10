# SPDX-License-Identifier: Apache-2.0
"""``linkedout compute-affinity`` — compute relationship affinity scores.

Sets affinity_score and dunbar_tier on every connection row for each user.
Safe to re-run -- scores are overwritten in place.
"""
import time

import click
from sqlalchemy import select

from linkedout.intelligence.scoring.affinity_scorer import AffinityScorer
from organization.entities.app_user_entity import AppUserEntity
from shared.infra.db.cli_db import cli_db_manager
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger
from shared.utilities.metrics import record_metric
from shared.utilities.operation_report import OperationCounts, OperationReport
from linkedout.cli_helpers import cli_logged

logger = get_logger(__name__, component="cli")


@click.command('compute-affinity')
@click.option('--dry-run', is_flag=True, help='Report stats only, do not compute')
@click.option('--force', is_flag=True, help='Recompute all (default: only unscored connections)')
@cli_logged("compute_affinity")
def compute_affinity_command(dry_run: bool, force: bool):
    """Calculate affinity scores and Dunbar tiers for all connections."""
    db_manager = cli_db_manager()
    with db_manager.get_session(DbSessionType.READ) as session:
        user_ids = [u.id for u in session.execute(
            select(AppUserEntity).where(AppUserEntity.is_active.is_(True))
        ).scalars().all()]

    click.echo(f'Computing affinity for {len(user_ids)} user(s)...')

    if dry_run:
        click.echo('Dry run -- no changes written.')
        return

    start_time = time.time()
    total = 0
    for uid in user_ids:
        with db_manager.get_session(DbSessionType.WRITE, app_user_id=uid) as session:
            scorer = AffinityScorer(session)
            count = scorer.compute_for_user(uid)
            click.echo(f'  {uid}: updated {count} connections')
            total += count

    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        f'Affinity computed for {total} connections across '
        f'{len(user_ids)} users in {duration_ms:.0f}ms'
    )
    record_metric("affinity_computed", total, duration_ms=duration_ms, users=len(user_ids))

    report = OperationReport(
        operation='compute-affinity',
        duration_ms=duration_ms,
        counts=OperationCounts(
            total=total,
            succeeded=total,
        ),
        next_steps=['Run `linkedout status` to view updated affinity stats'],
    )
    report_path = report.save()

    click.echo('\nResults:')
    click.echo(f'  Connections updated: {total:,}')
    click.echo(f'  Users processed:    {len(user_ids)}')

    click.echo('\nNext steps:')
    click.echo('  -> Run `linkedout status` to view updated affinity stats')

    try:
        from pathlib import Path
        display = '~/' + str(report_path.relative_to(Path.home()))
    except ValueError:
        display = str(report_path)
    click.echo(f'\nReport saved: {display}')
