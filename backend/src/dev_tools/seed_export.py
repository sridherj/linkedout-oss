# SPDX-License-Identifier: Apache-2.0
"""Export seed data from PostgreSQL to pg_dump files.

Maintainer-only script that connects to the production LinkedOut PostgreSQL
database and exports 6 company/reference seed tables into tiered pg_dump files
with a machine-readable manifest.

Profile data (crawled_profile, experience, education, profile_skill) is NOT
included — it ships separately via the demo pipeline (generate-demo-seed.py).

Usage:
    cd src && python -m dev_tools.seed_export --output seed-data/
"""
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import click
from sqlalchemy import inspect, text

from dev_tools.db.fixed_data import SYSTEM_USER_ID
from shared.config import get_config
from shared.infra.db.cli_db import cli_db_manager
from shared.infra.db.db_session_manager import DbSessionType
from shared.utils.checksum import compute_sha256

VERSION = "0.2.0"

# Tables in FK-safe order — company/reference data only.
# Profile data (crawled_profile, experience, education, profile_skill) ships
# via the demo pipeline, not the seed export.
SEED_TABLES = [
    "company",
    "company_alias",
    "role_alias",
    "funding_round",
    "startup_tracking",
    "growth_signal",
]

# No PII columns in company/reference tables.
PII_NULL_COLUMNS: dict[str, set[str]] = {}

# No columns to exclude from company/reference tables.
EXCLUDE_COLUMNS: dict[str, set[str]] = {}

# ── Tier company filter subqueries ────────────────────────────────────────────
# Core: companies where at least one crawled_profile has experience there
CORE_COMPANY_FILTER = (
    "SELECT DISTINCT c.id FROM company c "
    "JOIN experience e ON e.company_id = c.id "
    "JOIN crawled_profile cp ON cp.id = e.crawled_profile_id"
)

# Full: companies with employee count, funding rounds, or a size tier
# (no web_traffic_rank column exists; size_tier is the closest proxy)
FULL_COMPANY_FILTER = (
    "SELECT DISTINCT c.id FROM company c "
    "WHERE c.estimated_employee_count > 0 "
    "OR EXISTS (SELECT 1 FROM funding_round fr WHERE fr.company_id = c.id) "
    "OR c.size_tier IS NOT NULL"
)

TIER_COMPANY_FILTER = {
    "core": CORE_COMPANY_FILTER,
    "full": FULL_COMPANY_FILTER,
}

# Which column to filter by tier's company set. None = export all rows.
TABLE_FILTER_COLUMN = {
    "company":          "id",
    "company_alias":    "company_id",
    "role_alias":       None,           # no FK — export all
    "funding_round":    "company_id",
    "startup_tracking": "company_id",
    "growth_signal":    "company_id",
}


# ── Query builders ────────────────────────────────────────────────────────────

def _build_select(table_name: str, columns: list[dict]) -> str:
    """Build SELECT clause, NULLing PII columns."""
    pii = PII_NULL_COLUMNS.get(table_name, set())
    parts = []
    for col in columns:
        name = col["name"]
        parts.append(f"NULL AS {name}" if name in pii else name)
    return ", ".join(parts)


def _build_export_query(table_name: str, columns: list[dict], tier: str) -> str:
    """Build the full SELECT … WHERE … ORDER BY for a table + tier."""
    select_clause = _build_select(table_name, columns)
    query = f"SELECT {select_clause} FROM {table_name}"

    fk_col = TABLE_FILTER_COLUMN[table_name]
    if fk_col is not None:
        company_filter = TIER_COMPANY_FILTER[tier]
        query += f" WHERE {fk_col} IN ({company_filter})"

    query += " ORDER BY id"
    return query


# ── Column helpers ────────────────────────────────────────────────────────────

def _get_columns(inspector, table_name: str) -> list[dict]:
    """Get column metadata, excluding columns we don't export."""
    excluded = EXCLUDE_COLUMNS.get(table_name, set())
    return [c for c in inspector.get_columns(table_name) if c["name"] not in excluded]


def _get_deterministic_timestamp(session, tier: str) -> str:
    """Derive a deterministic timestamp from source data for idempotent output."""
    company_filter = TIER_COMPANY_FILTER[tier]
    result = session.execute(text(
        f"SELECT MAX(c.updated_at) FROM company c WHERE c.id IN ({company_filter})"
    )).scalar()
    if result and not isinstance(result, str):
        return result.isoformat()
    return str(result) if result else "1970-01-01T00:00:00+00:00"


# ── Staging schema helpers ───────────────────────────────────────────────────

def _create_staging_schema(session, inspector, tier: str):
    """Create _seed_staging schema with filtered data for a tier."""
    session.execute(text("DROP SCHEMA IF EXISTS _seed_staging CASCADE"))
    session.execute(text("CREATE SCHEMA _seed_staging"))
    for table_name in SEED_TABLES:
        columns = _get_columns(inspector, table_name)
        query = _build_export_query(table_name, columns, tier)
        session.execute(text(f"CREATE TABLE _seed_staging.{table_name} AS {query}"))
    session.commit()


def _pg_dump_staging(db_url: str, output_path: Path):
    """Run pg_dump on the _seed_staging schema and write to output_path."""
    result = subprocess.run(
        ["pg_dump", "-Fc", "--schema=_seed_staging", "--no-owner", str(db_url)],
        capture_output=True, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed (exit {result.returncode}): {result.stderr.decode()[:500]}")
    output_path.write_bytes(result.stdout)


def _drop_staging_schema(session):
    """Drop the _seed_staging schema."""
    session.execute(text("DROP SCHEMA IF EXISTS _seed_staging CASCADE"))
    session.commit()


# ── Core export logic ─────────────────────────────────────────────────────────

def _export_tier(session, inspector, tier: str, output_dir: Path, dry_run: bool) -> dict | None:
    """Export one tier to a pg_dump file. Returns file metadata or None."""
    click.echo(f"\n{'=' * 60}")
    click.echo(f"Tier: {tier}")
    click.echo(f"{'=' * 60}")

    # Count qualifying companies
    company_count = session.execute(text(
        f"SELECT COUNT(*) FROM ({TIER_COMPANY_FILTER[tier]}) _sub"
    )).scalar()
    click.echo(f"  Qualifying companies: {company_count:,}")

    if company_count == 0:
        click.echo("  No companies found. Skipping.")
        return None

    table_counts: dict[str, int] = {}

    if dry_run:
        for table_name in SEED_TABLES:
            columns = _get_columns(inspector, table_name)
            query = _build_export_query(table_name, columns, tier)
            row_count = session.execute(text(f"SELECT COUNT(*) FROM ({query}) _sub")).scalar()
            table_counts[table_name] = row_count
            click.echo(f"  {table_name}: {row_count:,} rows")
        click.echo(f"  Total: {sum(table_counts.values()):,} rows")
        return None

    # Create staging schema with filtered data
    _create_staging_schema(session, inspector, tier)

    # Count rows in staging tables (for manifest)
    for table_name in SEED_TABLES:
        count = session.execute(text(f"SELECT COUNT(*) FROM _seed_staging.{table_name}")).scalar()
        table_counts[table_name] = count
        click.echo(f"  Exporting {table_name}... {count:,} rows")

    # pg_dump the staging schema
    filepath = output_dir / f"seed-{tier}.dump"
    db_url = get_config().database_url  # Decision #6: use get_config(), not session.get_bind().url
    _pg_dump_staging(db_url, filepath)

    # Cleanup
    _drop_staging_schema(session)

    # Compute checksum
    sha256 = compute_sha256(filepath)
    size_bytes = filepath.stat().st_size
    click.echo(f"  -> {filepath.name}: {size_bytes:,} bytes (sha256: {sha256[:12]}...)")

    return {
        "name": filepath.name,
        "tier": tier,
        "path": filepath,
        "size_bytes": size_bytes,
        "sha256": sha256,
        "table_counts": table_counts,
    }


def _generate_manifest(output_dir: Path, files: list[dict]) -> None:
    """Generate seed-manifest.json alongside the dump files."""
    manifest = {
        "version": VERSION,
        "format": "pgdump",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": [
            {
                "name": f["name"],
                "tier": f["tier"],
                "size_bytes": f["size_bytes"],
                "sha256": f["sha256"],
                "table_counts": f["table_counts"],
            }
            for f in files
        ],
    }
    path = output_dir / "seed-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    click.echo(f"\nManifest: {path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

@click.command()
@click.option("--output", required=True, type=click.Path(), help="Output directory")
@click.option("--tiers", default="core,full", help="Comma-separated tiers (default: core,full)")
@click.option("--dry-run", is_flag=True, help="Show counts without writing files")
def main(output: str, tiers: str, dry_run: bool):
    """Export seed data from PostgreSQL to pg_dump files."""
    db_manager = cli_db_manager()
    output_dir = Path(output)
    tier_list = [t.strip() for t in tiers.split(",")]

    for t in tier_list:
        if t not in ("core", "full"):
            raise click.BadParameter(f"Unknown tier: {t}")

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Seed Export v{VERSION}")
    click.echo(f"Output: {output_dir}")
    click.echo(f"Tiers: {', '.join(tier_list)}")
    if dry_run:
        click.echo("[DRY RUN]")

    start = time.time()
    exported: list[dict] = []

    with db_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
        inspector = inspect(session.get_bind())
        for tier in tier_list:
            result = _export_tier(session, inspector, tier, output_dir, dry_run)
            if result:
                exported.append(result)

    if exported and not dry_run:
        _generate_manifest(output_dir, exported)

    elapsed = time.time() - start
    click.echo(f"\n{'=' * 60}")
    click.echo("Summary")
    click.echo(f"{'=' * 60}")
    for f in exported:
        total = sum(f["table_counts"].values())
        click.echo(f"  {f['name']}: {total:,} rows, {f['size_bytes']:,} bytes")
    if not exported and not dry_run:
        click.echo("  No data exported.")
    click.echo(f"  Elapsed: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
