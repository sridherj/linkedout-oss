# SPDX-License-Identifier: Apache-2.0
"""Generate a small PostgreSQL test fixture for seed data pipeline tests.

Creates ``test-seed-core.dump`` and ``seed-manifest.json`` with ~10 rows per
table using synthetic data.  Requires a running PostgreSQL instance.

Runnable standalone to regenerate the fixture if the schema changes::

    cd backend/tests/fixtures
    python generate_test_seed.py [db_url] [output_path]
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
# Add backend/src to Python path for entity imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))


# ── Constants ────────────────────────────────────────────────────────

STAGING_SCHEMA = "_seed_staging"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _psql(db_url: str, sql: str, label: str = "") -> None:
    """Execute SQL via psql, raising on failure."""
    result = subprocess.run(
        ["psql", db_url, "-c", sql],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"psql failed{f' ({label})' if label else ''}: {result.stderr.strip()}"
        )


def _create_schema(db_url: str) -> None:
    """Create seed tables from entity metadata in _seed_staging schema."""
    from sqlalchemy import create_engine

    from common.entities.base_entity import Base
    from linkedout.company.entities.company_entity import CompanyEntity  # noqa: F401
    from linkedout.company_alias.entities.company_alias_entity import CompanyAliasEntity  # noqa: F401
    from linkedout.funding.entities.funding_round_entity import FundingRoundEntity  # noqa: F401
    from linkedout.funding.entities.growth_signal_entity import GrowthSignalEntity  # noqa: F401
    from linkedout.funding.entities.startup_tracking_entity import StartupTrackingEntity  # noqa: F401
    from linkedout.role_alias.entities.role_alias_entity import RoleAliasEntity  # noqa: F401

    seed_tables = [
        CompanyEntity.__table__,
        CompanyAliasEntity.__table__,
        RoleAliasEntity.__table__,
        FundingRoundEntity.__table__,
        StartupTrackingEntity.__table__,
        GrowthSignalEntity.__table__,
    ]

    engine = create_engine(
        db_url,
        connect_args={"options": f"-c search_path={STAGING_SCHEMA},public"},
    )
    Base.metadata.create_all(engine, tables=seed_tables)
    engine.dispose()
    print(f"Created {len(seed_tables)} tables in {STAGING_SCHEMA} schema")


def _insert_data(db_url: str) -> dict[str, int]:
    """Insert synthetic rows in native PG types. Returns table_counts."""
    ts = _now_iso()
    S = STAGING_SCHEMA

    # --- Companies (10) ---
    industries = [
        "Technology", "Finance", "Healthcare", "Education", "Retail",
        "Energy", "Media", "SaaS", "AI", "Biotech",
    ]
    company_parts = []
    for i in range(1, 11):
        enrichment = "ARRAY['linkedin','pdl']" if i <= 5 else "NULL"
        enriched_at = f"'{ts}'::timestamptz" if i <= 5 else "NULL"
        pdl_id = f"'pdl_{i}'" if i <= 3 else "NULL"
        wikidata_id = f"'Q{1000 + i}'" if i <= 2 else "NULL"
        city = "San Francisco" if i <= 5 else "New York"
        emp_range = "51-200" if i <= 5 else "201-500"
        size = "SMB" if i <= 5 else "Mid-Market"
        company_parts.append(
            f"('co_test_{i:03d}', 'Test Company {i}', 'test company {i}', "
            f"'https://linkedin.com/company/test-co-{i}', 'test-co-{i}', "
            f"'https://testco{i}.example.com', 'testco{i}.example.com', "
            f"'{industries[i - 1]}', {2000 + i}, "
            f"'{city}', 'US', '{emp_range}', {100 * i}, "
            f"'{size}', {i * 3}, NULL, "
            f"{enrichment}, {enriched_at}, {pdl_id}, {wikidata_id}, "
            f"'{ts}', '{ts}', NULL, NULL, NULL, TRUE, 1)"
        )

    _psql(db_url, (
        f"INSERT INTO {S}.company (id, canonical_name, normalized_name, "
        f"linkedin_url, universal_name, website, domain, industry, founded_year, "
        f"hq_city, hq_country, employee_count_range, estimated_employee_count, "
        f"size_tier, network_connection_count, parent_company_id, "
        f"enrichment_sources, enriched_at, pdl_id, wikidata_id, "
        f"created_at, updated_at, deleted_at, created_by, updated_by, "
        f"is_active, version) VALUES\n"
        + ",\n".join(company_parts) + ";"
    ), "companies")

    # --- Company Aliases (15) ---
    alias_parts = []
    for i in range(1, 16):
        co_idx = ((i - 1) % 10) + 1
        source = "linkedin" if i % 2 == 0 else "manual"
        alias_parts.append(
            f"('ca_test_{i:03d}', 'TC{co_idx} Alias {i}', 'co_test_{co_idx:03d}', "
            f"'{source}', '{ts}', '{ts}', NULL, NULL, NULL, TRUE, 1)"
        )

    _psql(db_url, (
        f"INSERT INTO {S}.company_alias (id, alias_name, company_id, source, "
        f"created_at, updated_at, deleted_at, created_by, updated_by, "
        f"is_active, version) VALUES\n"
        + ",\n".join(alias_parts) + ";"
    ), "company_aliases")

    # --- Role Aliases (10) ---
    titles = [
        ("SWE", "Software Engineer", "mid", "engineering"),
        ("Sr SWE", "Senior Software Engineer", "senior", "engineering"),
        ("PM", "Product Manager", "mid", "product"),
        ("Sr PM", "Senior Product Manager", "senior", "product"),
        ("DS", "Data Scientist", "mid", "data"),
        ("ML Eng", "Machine Learning Engineer", "mid", "engineering"),
        ("VP Eng", "VP of Engineering", "executive", "engineering"),
        ("CTO", "Chief Technology Officer", "c-suite", "engineering"),
        ("Designer", "Product Designer", "mid", "design"),
        ("DevOps", "DevOps Engineer", "mid", "engineering"),
    ]
    role_parts = []
    for i, (alias, canonical, seniority, area) in enumerate(titles, 1):
        role_parts.append(
            f"('ra_test_{i:03d}', '{alias}', '{canonical}', "
            f"'{seniority}', '{area}', "
            f"'{ts}', '{ts}', NULL, NULL, NULL, TRUE, 1)"
        )

    _psql(db_url, (
        f"INSERT INTO {S}.role_alias (id, alias_title, canonical_title, "
        f"seniority_level, function_area, "
        f"created_at, updated_at, deleted_at, created_by, updated_by, "
        f"is_active, version) VALUES\n"
        + ",\n".join(role_parts) + ";"
    ), "role_aliases")

    # --- Funding Rounds (8 across 4 companies) ---
    rounds_data = [
        ("co_test_001", "Seed", "2020-03-15", 2_000_000, ["Sequoia"], ["Sequoia", "YC"]),
        ("co_test_001", "Series A", "2022-01-10", 15_000_000, ["a16z"], ["a16z", "Sequoia"]),
        ("co_test_002", "Seed", "2019-06-01", 1_500_000, ["Founders Fund"], ["Founders Fund"]),
        ("co_test_002", "Series A", "2021-09-20", 12_000_000, ["Benchmark"], ["Benchmark", "Founders Fund"]),
        ("co_test_003", "Seed", "2021-01-05", 3_000_000, ["Greylock"], ["Greylock"]),
        ("co_test_003", "Series A", "2023-04-15", 20_000_000, ["Accel"], ["Accel", "Greylock"]),
        ("co_test_004", "Seed", "2022-07-01", 5_000_000, ["Index"], ["Index", "SV Angel"]),
        ("co_test_004", "Series A", "2024-02-28", 25_000_000, ["Tiger Global"], ["Tiger Global", "Index"]),
    ]
    funding_parts = []
    for i, (co_id, rtype, date, amount, lead, all_inv) in enumerate(rounds_data, 1):
        lead_arr = "ARRAY[" + ",".join(f"'{x}'" for x in lead) + "]"
        all_arr = "ARRAY[" + ",".join(f"'{x}'" for x in all_inv) + "]"
        funding_parts.append(
            f"('fr_test_{i:03d}', '{co_id}', '{rtype}', '{date}'::date, "
            f"{amount}, {lead_arr}, {all_arr}, "
            f"'https://crunchbase.com/round/{i}', 8, "
            f"'{ts}', '{ts}', NULL, NULL, NULL, TRUE, 1)"
        )

    _psql(db_url, (
        f"INSERT INTO {S}.funding_round (id, company_id, round_type, "
        f"announced_on, amount_usd, lead_investors, all_investors, "
        f"source_url, confidence, "
        f"created_at, updated_at, deleted_at, created_by, updated_by, "
        f"is_active, version) VALUES\n"
        + ",\n".join(funding_parts) + ";"
    ), "funding_rounds")

    # --- Startup Tracking (5) ---
    tracking_parts = []
    for i in range(1, 6):
        watching = "TRUE" if i <= 3 else "FALSE"
        vertical = "AI Agents" if i <= 2 else "SaaS"
        funding_stage = "Series A" if i <= 3 else "Seed"
        arr = str(1_000_000 * i) if i <= 3 else "NULL"
        arr_date = "'2024-06-01'::date" if i <= 3 else "NULL"
        arr_conf = "7" if i <= 3 else "NULL"
        round_count = 2 if i <= 3 else 1
        tracking_parts.append(
            f"('st_test_{i:03d}', 'co_test_{i:03d}', {watching}, "
            f"'Tracking test company {i}', '{vertical}', 'Developer Tools', "
            f"'{funding_stage}', {10_000_000 * i}, '2024-0{i}-01'::date, "
            f"{round_count}, {arr}, {arr_date}, {arr_conf}, "
            f"'{ts}', '{ts}', NULL, NULL, NULL, TRUE, 1)"
        )

    _psql(db_url, (
        f"INSERT INTO {S}.startup_tracking (id, company_id, watching, "
        f"description, vertical, sub_category, funding_stage, "
        f"total_raised_usd, last_funding_date, round_count, "
        f"estimated_arr_usd, arr_signal_date, arr_confidence, "
        f"created_at, updated_at, deleted_at, created_by, updated_by, "
        f"is_active, version) VALUES\n"
        + ",\n".join(tracking_parts) + ";"
    ), "startup_tracking")

    # --- Growth Signals (12) ---
    signal_parts = []
    for i in range(1, 13):
        co_idx = ((i - 1) % 5) + 1
        sig_type = "headcount" if i % 2 == 0 else "revenue"
        month = ((i - 1) % 12) + 1
        value_text = f"${100 * i}K" if i % 2 != 0 else f"{10 * i} employees"
        signal_parts.append(
            f"('gs_test_{i:03d}', 'co_test_{co_idx:03d}', '{sig_type}', "
            f"'2024-{month:02d}-15'::date, {100_000 * i}, "
            f"'{value_text}', 'https://example.com/signal/{i}', {min(i, 10)}, "
            f"'{ts}', '{ts}', NULL, NULL, NULL, TRUE, 1)"
        )

    _psql(db_url, (
        f"INSERT INTO {S}.growth_signal (id, company_id, signal_type, "
        f"signal_date, value_numeric, value_text, source_url, confidence, "
        f"created_at, updated_at, deleted_at, created_by, updated_by, "
        f"is_active, version) VALUES\n"
        + ",\n".join(signal_parts) + ";"
    ), "growth_signals")

    return {
        "company": 10,
        "company_alias": 15,
        "role_alias": 10,
        "funding_round": 8,
        "startup_tracking": 5,
        "growth_signal": 12,
    }


def generate(
    base_db_url: str = "postgresql://linkedout:linkedout@localhost:5432/linkedout",
    output_path: Path | None = None,
) -> Path:
    """Generate the test fixture pg_dump file and seed manifest.

    1. Creates a temporary database.
    2. Creates ``_seed_staging`` schema with tables from entity metadata.
    3. Inserts synthetic data in native PG types.
    4. Runs ``pg_dump`` to produce a ``.dump`` file.
    5. Generates ``seed-manifest.json``.
    6. Drops the staging schema.

    Args:
        base_db_url: PostgreSQL connection URL pointing to any existing database.
        output_path: Where to write the dump. Defaults to
            ``test-seed-core.dump`` in the same directory as this script.

    Returns:
        Path to the generated dump file.
    """
    if output_path is None:
        output_path = Path(__file__).parent / "test-seed-core.dump"

    manifest_path = output_path.parent / "seed-manifest.json"

    # Use the provided database directly (no temp database needed)
    db_url = base_db_url

    # ── Clean slate ──────────────────────────────────────────────
    _psql(db_url, f"DROP SCHEMA IF EXISTS {STAGING_SCHEMA} CASCADE;", "drop schema")
    _psql(db_url, f"CREATE SCHEMA {STAGING_SCHEMA};", "create schema")

    try:
        _create_schema(db_url)
        table_counts = _insert_data(db_url)

        # ── pg_dump ──────────────────────────────────────────────
        result = subprocess.run(
            [
                "pg_dump", "-Fc",
                f"--schema={STAGING_SCHEMA}",
                "--no-owner",
                db_url,
            ],
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {result.stderr.decode().strip()}")

        output_path.write_bytes(result.stdout)
        print(f"Generated: {output_path} ({output_path.stat().st_size:,} bytes)")

        # ── seed-manifest.json ───────────────────────────────────
        manifest = {
            "version": "0.0.1-test",
            "format": "pgdump",
            "tier": "core",
            "created_at": _now_iso(),
            "table_counts": table_counts,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Generated: {manifest_path}")

    finally:
        _psql(db_url, f"DROP SCHEMA IF EXISTS {STAGING_SCHEMA} CASCADE;", "cleanup")

    # ── Summary ──────────────────────────────────────────────────
    print(f"Tables: {len(table_counts)}")
    for table, count in table_counts.items():
        print(f"  {table}: {count} rows")
    print(f"  Total: {sum(table_counts.values())} rows")

    return output_path


if __name__ == "__main__":
    db_url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "postgresql://linkedout:linkedout@localhost:5432/linkedout"
    )
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    generate(base_db_url=db_url, output_path=out)
