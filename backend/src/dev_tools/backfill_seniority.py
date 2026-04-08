# SPDX-License-Identifier: Apache-2.0
"""Backfill seniority_level and function_area on crawled_profile using role_alias lookups.

Iterates profiles where seniority_level is NULL and current_position is set,
then does an exact-match lookup against role_alias.alias_title.
"""
import click
from sqlalchemy import select

from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.role_alias.repositories.role_alias_repository import RoleAliasRepository
from dev_tools.db.fixed_data import SYSTEM_USER_ID
from shared.infra.db.db_session_manager import DbSessionType, db_session_manager


def main(dry_run: bool = False, limit: int = 0) -> int:
    with db_session_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
        query = (
            select(CrawledProfileEntity)
            .where(
                CrawledProfileEntity.seniority_level.is_(None),
                CrawledProfileEntity.current_position.isnot(None),
            )
        )
        if limit:
            query = query.limit(limit)

        profiles = session.execute(query).scalars().all()
        click.echo(f'Profiles to process: {len(profiles)}')

        repo = RoleAliasRepository(session)
        matched = 0
        for profile in profiles:
            alias = repo.get_by_alias_title(profile.current_position)
            if alias:
                matched += 1
                if not dry_run:
                    profile.seniority_level = alias.seniority_level
                    profile.function_area = alias.function_area

        if dry_run:
            click.echo(f'Dry run — would update {matched}/{len(profiles)} profiles.')
        else:
            click.echo(f'Updated {matched}/{len(profiles)} profiles.')

    return 0
