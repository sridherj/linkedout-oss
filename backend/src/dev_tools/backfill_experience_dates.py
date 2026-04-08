# SPDX-License-Identifier: Apache-2.0
"""Backfill experience end_year and start_year from dates and text fields.

Populates:
  - end_year from end_date (where end_date IS NOT NULL AND end_year IS NULL)
  - end_year from end_date_text via regex year extraction (where both end_date and end_year are NULL)
  - start_year from start_date (where start_date IS NOT NULL AND start_year IS NULL)
"""
import re

import click
from sqlalchemy import text

from shared.infra.db.db_session_manager import DbSessionType, db_session_manager

_YEAR_RE = re.compile(r'\b(19|20)\d{2}\b')


def _extract_year(text_val: str | None) -> int | None:
    if not text_val:
        return None
    m = _YEAR_RE.search(text_val)
    return int(m.group()) if m else None


def main(dry_run: bool = False) -> int:
    """Backfill experience date fields. Returns 0 on success, 1 on failure."""
    try:
        with db_session_manager.get_session(DbSessionType.WRITE) as session:
            # 1. end_year from end_date
            result = session.execute(text("""
                UPDATE experience
                SET end_year = EXTRACT(YEAR FROM end_date)::int
                WHERE end_date IS NOT NULL
                  AND end_year IS NULL
            """))
            end_year_from_date = result.rowcount  # type: ignore[union-attr]

            # 2. start_year from start_date
            result = session.execute(text("""
                UPDATE experience
                SET start_year = EXTRACT(YEAR FROM start_date)::int
                WHERE start_date IS NOT NULL
                  AND start_year IS NULL
            """))
            start_year_from_date = result.rowcount  # type: ignore[union-attr]

            # 3. end_year from end_date_text (regex in Python — fetch rows, update in batches)
            rows = session.execute(text("""
                SELECT id, end_date_text
                FROM experience
                WHERE end_date IS NULL
                  AND end_year IS NULL
                  AND end_date_text IS NOT NULL
                  AND end_date_text NOT ILIKE '%present%'
            """)).fetchall()

            text_updates = [
                {"id": row[0], "year": _extract_year(row[1])}
                for row in rows
                if _extract_year(row[1]) is not None
            ]

            if text_updates and not dry_run:
                session.execute(
                    text("UPDATE experience SET end_year = :year WHERE id = :id"),
                    text_updates,
                )
            end_year_from_text = len(text_updates)

            click.echo("=== Experience Date Backfill ===")
            click.echo(f"  end_year from end_date:      {end_year_from_date}")
            click.echo(f"  start_year from start_date:  {start_year_from_date}")
            click.echo(f"  end_year from end_date_text: {end_year_from_text}")
            click.echo(f"  Total rows updated:          {end_year_from_date + start_year_from_date + end_year_from_text}")

            if dry_run:
                click.echo("\nDry run — no DB writes performed.")
                session.rollback()

        return 0

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        return 1
