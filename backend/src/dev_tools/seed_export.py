# SPDX-License-Identifier: Apache-2.0
"""Export seed data from PostgreSQL to SQLite files.

Maintainer-only script that connects to the production LinkedOut PostgreSQL
database and exports 10 seed tables into tiered SQLite files with a
machine-readable manifest.

Usage:
    cd src && python -m dev_tools.seed_export --output seed-data/
"""
import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import click
from sqlalchemy import inspect, text

from shared.infra.db.db_session_manager import db_session_manager, DbSessionType
from shared.utils.checksum import compute_sha256

VERSION = "0.1.0"

# Tables in FK-safe order (matches import order from shared context)
SEED_TABLES = [
    "company",
    "company_alias",
    "role_alias",
    "funding_round",
    "startup_tracking",
    "growth_signal",
    "crawled_profile",
    "experience",
    "education",
    "profile_skill",
]

# PII columns to NULL during export (crawled_profile only per spec).
# Entity has no email/phone columns; these are the actual PII-bearing fields:
#   notes        — BaseEntity internal notes
#   raw_profile  — raw JSON payload that may contain PII
#   source_app_user_id — FK to internal app_user (not in seed tables)
PII_NULL_COLUMNS = {
    "crawled_profile": {"notes", "raw_profile", "source_app_user_id"},
}

# Columns to exclude entirely (pgvector types have no SQLite equivalent;
# embeddings are explicitly excluded from seed data per decision doc).
EXCLUDE_COLUMNS = {
    "crawled_profile": {
        "embedding_openai", "embedding_nomic", "embedding_model",
        "embedding_dim", "embedding_updated_at", "search_vector",
    },
}

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

# How each table relates to the tier filter.
# (filter_column, filter_source) — None means export all rows.
TABLE_FILTER = {
    "company":          ("id",                   "company"),
    "company_alias":    ("company_id",           "company"),
    "role_alias":       (None,                   None),      # no FK — export all
    "funding_round":    ("company_id",           "company"),
    "startup_tracking": ("company_id",           "company"),
    "growth_signal":    ("company_id",           "company"),
    "crawled_profile":  ("id",                   "profile"),
    "experience":       ("crawled_profile_id",   "profile"),
    "education":        ("crawled_profile_id",   "profile"),
    "profile_skill":    ("crawled_profile_id",   "profile"),
}


# ── Type mapping ──────────────────────────────────────────────────────────────

def _sqlite_type_for(pg_type_str: str) -> str:
    """Map a PostgreSQL type string to a SQLite storage type."""
    lower = pg_type_str.lower()
    if "[]" in lower or "array" in lower:
        return "TEXT"
    for kw in ("varchar", "character varying", "text", "char"):
        if kw in lower:
            return "TEXT"
    for kw in ("bigint", "smallint", "integer", "int"):
        if kw in lower:
            return "INTEGER"
    if "bool" in lower:
        return "INTEGER"
    for kw in ("timestamp", "date"):
        if kw in lower:
            return "TEXT"
    for kw in ("double", "float", "real", "numeric", "decimal"):
        if kw in lower:
            return "REAL"
    return "TEXT"


def _is_array(col: dict) -> bool:
    t = str(col["type"]).upper()
    return "[]" in t or "ARRAY" in t


def _is_bool(col: dict) -> bool:
    return "BOOL" in str(col["type"]).upper()


def _is_temporal(col: dict) -> bool:
    t = str(col["type"]).upper()
    return "TIMESTAMP" in t or "DATE" in t


# ── Query builders ────────────────────────────────────────────────────────────

def _profile_filter_sql(company_filter: str) -> str:
    """Subquery: profile IDs with experience at qualifying companies."""
    return (
        "SELECT DISTINCT e.crawled_profile_id FROM experience e "
        f"WHERE e.company_id IN ({company_filter})"
    )


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

    fk_col, filter_type = TABLE_FILTER[table_name]
    if fk_col is not None:
        company_filter = TIER_COMPANY_FILTER[tier]
        if filter_type == "company":
            query += f" WHERE {fk_col} IN ({company_filter})"
        else:  # profile
            query += f" WHERE {fk_col} IN ({_profile_filter_sql(company_filter)})"

    query += " ORDER BY id"
    return query


# ── Column helpers ────────────────────────────────────────────────────────────

def _get_columns(inspector, table_name: str) -> list[dict]:
    """Get column metadata, excluding columns we don't export."""
    excluded = EXCLUDE_COLUMNS.get(table_name, set())
    return [c for c in inspector.get_columns(table_name) if c["name"] not in excluded]


def _convert_row(row, columns: list[dict]) -> tuple:
    """Convert a PostgreSQL row to SQLite-compatible values."""
    values = list(row)
    for i, col in enumerate(columns):
        val = values[i]
        if val is None:
            continue
        if _is_array(col):
            values[i] = json.dumps(val)
        elif _is_bool(col):
            values[i] = int(val)
        elif _is_temporal(col) and not isinstance(val, str):
            values[i] = val.isoformat()
    return tuple(values)


# ── SQLite helpers ────────────────────────────────────────────────────────────

def _create_sqlite_table(cursor: sqlite3.Cursor, table_name: str, columns: list[dict]):
    """Create a SQLite table mirroring the PostgreSQL schema."""
    col_defs = []
    for col in columns:
        sqlite_type = _sqlite_type_for(str(col["type"]))
        parts = [col["name"], sqlite_type]
        if col["name"] == "id":
            parts.append("PRIMARY KEY")
        elif not col.get("nullable", True):
            parts.append("NOT NULL")
        col_defs.append(" ".join(parts))
    cursor.execute(f"CREATE TABLE {table_name} ({', '.join(col_defs)})")


def _get_deterministic_timestamp(session, tier: str) -> str:
    """Derive a deterministic timestamp from source data for idempotent output."""
    company_filter = TIER_COMPANY_FILTER[tier]
    result = session.execute(text(
        f"SELECT MAX(c.updated_at) FROM company c WHERE c.id IN ({company_filter})"
    )).scalar()
    if result and not isinstance(result, str):
        return result.isoformat()
    return str(result) if result else "1970-01-01T00:00:00+00:00"


# ── Core export logic ─────────────────────────────────────────────────────────

def _export_tier(session, inspector, tier: str, output_dir: Path, dry_run: bool) -> dict | None:
    """Export one tier to a SQLite file. Returns file metadata or None."""
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

    # Create SQLite file
    filename = f"seed-{tier}.sqlite"
    filepath = output_dir / filename
    if filepath.exists():
        filepath.unlink()

    conn = sqlite3.connect(str(filepath))
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=DELETE")
    cursor.execute("PRAGMA synchronous=FULL")

    for table_name in SEED_TABLES:
        columns = _get_columns(inspector, table_name)
        col_names = [c["name"] for c in columns]

        _create_sqlite_table(cursor, table_name, columns)

        query = _build_export_query(table_name, columns, tier)
        rows = session.execute(text(query)).fetchall()
        converted = [_convert_row(r, columns) for r in rows]

        if converted:
            placeholders = ", ".join(["?"] * len(col_names))
            cursor.executemany(
                f"INSERT INTO {table_name} ({', '.join(col_names)}) VALUES ({placeholders})",
                converted,
            )

        table_counts[table_name] = len(converted)
        click.echo(f"  Exporting {table_name}... {len(converted):,} rows")

    # _metadata table — uses deterministic timestamp for idempotent output
    deterministic_ts = _get_deterministic_timestamp(session, tier)
    source_hash = hashlib.sha256(
        json.dumps(table_counts, sort_keys=True).encode()
    ).hexdigest()[:16]

    cursor.execute("CREATE TABLE _metadata (key TEXT PRIMARY KEY, value TEXT)")
    cursor.executemany("INSERT INTO _metadata (key, value) VALUES (?, ?)", [
        ("version", VERSION),
        ("created_at", deterministic_ts),
        ("source_db_hash", source_hash),
        ("table_counts", json.dumps(table_counts, sort_keys=True)),
    ])

    conn.commit()
    cursor.execute("VACUUM")
    conn.close()

    size_bytes = filepath.stat().st_size
    sha256 = compute_sha256(filepath)
    click.echo(f"  -> {filename}: {size_bytes:,} bytes (sha256: {sha256[:12]}...)")

    return {
        "name": filename,
        "tier": tier,
        "path": filepath,
        "size_bytes": size_bytes,
        "sha256": sha256,
        "table_counts": table_counts,
    }


def _generate_manifest(output_dir: Path, files: list[dict]) -> None:
    """Generate seed-manifest.json alongside the SQLite files."""
    manifest = {
        "version": VERSION,
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
    """Export seed data from PostgreSQL to SQLite files."""
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

    with db_session_manager.get_session(DbSessionType.READ) as session:
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
