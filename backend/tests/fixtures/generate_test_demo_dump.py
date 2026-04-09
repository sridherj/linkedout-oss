# SPDX-License-Identifier: Apache-2.0
"""Generate a synthetic demo dump fixture for CI and integration tests.

Creates ``demo-seed-test.dump`` — a small pg_dump-format file containing
~10 profiles with pre-computed embeddings. This is distinct from the
``generate_test_seed.py`` script which produces a SQLite fixture for
seed pipeline tests.

Usage::

    # Requires a running PostgreSQL with pgvector
    cd backend/tests/fixtures
    python generate_test_demo_dump.py

The generated dump is committed to the repo so CI can restore it without
downloading the real ~100 MB demo dump from GitHub Releases.
"""
from __future__ import annotations

import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend/src to Python path for entity imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))


# ── Constants ────────────────────────────────────────────────────────

DEMO_DB_NAME = "linkedout_demo_test_fixture"
NUM_PROFILES = 10
NUM_COMPANIES = 15
NUM_EXPERIENCES = 50
NUM_EDUCATIONS = 20
NUM_SKILLS = 30
EMBEDDING_DIM = 768  # nomic-embed-text dimension

# Demo org data for connection FK requirements
DEMO_TENANT_ID = "tenant_demo_001"
DEMO_BU_ID = "bu_demo_001"
DEMO_APP_USER_ID = "usr_demo_001"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _random_embedding(dim: int = EMBEDDING_DIM) -> str:
    """Generate a random unit-norm embedding vector as a pgvector literal."""
    vec = [random.gauss(0, 1) for _ in range(dim)]
    norm = sum(x * x for x in vec) ** 0.5
    normalized = [x / norm for x in vec]
    return "[" + ",".join(f"{v:.6f}" for v in normalized) + "]"


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


def generate(
    base_db_url: str = "postgresql://linkedout:linkedout@localhost:5432/linkedout",
    output_path: Path | None = None,
) -> Path:
    """Generate the synthetic demo dump fixture.

    1. Creates a temporary database with pgvector enabled.
    2. Creates the schema from entity metadata (no hand-written DDL).
    3. Inserts synthetic data with pre-computed embeddings.
    4. Runs ``pg_dump`` to produce a ``.dump`` file.
    5. Drops the temporary database.

    Args:
        base_db_url: PostgreSQL connection URL (used for admin commands).
        output_path: Where to write the dump. Defaults to
            ``demo-seed-test.dump`` in the same directory as this script.

    Returns:
        Path to the generated dump file.
    """
    if output_path is None:
        output_path = Path(__file__).parent / "demo-seed-test.dump"

    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(base_db_url)
    maintenance_url = urlunparse(parsed._replace(path="/postgres"))
    fixture_db_url = urlunparse(parsed._replace(path=f"/{DEMO_DB_NAME}"))

    # ── Create database ──────────────────────────────────────────
    _psql(maintenance_url, f'DROP DATABASE IF EXISTS "{DEMO_DB_NAME}";', "drop")
    _psql(maintenance_url, f'CREATE DATABASE "{DEMO_DB_NAME}";', "create")

    try:
        _psql(fixture_db_url, "CREATE EXTENSION IF NOT EXISTS vector;", "pgvector")
        _create_schema(fixture_db_url)
        _insert_data(fixture_db_url)

        # ── pg_dump ──────────────────────────────────────────────
        result = subprocess.run(
            ["pg_dump", "-Fc", "--no-owner", fixture_db_url],
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {result.stderr.decode().strip()}")

        output_path.write_bytes(result.stdout)
        print(f"Generated: {output_path} ({output_path.stat().st_size:,} bytes)")

    finally:
        # Drop temporary database
        _psql(maintenance_url, f'DROP DATABASE IF EXISTS "{DEMO_DB_NAME}";', "cleanup")

    return output_path


def _create_schema(db_url: str) -> None:
    """Create demo tables from entity metadata — no hand-written DDL."""
    from sqlalchemy import create_engine

    from common.entities.base_entity import Base
    # Import entities to register their table metadata with Base.metadata
    from linkedout.company.entities.company_entity import CompanyEntity  # noqa: F401
    from linkedout.connection.entities.connection_entity import ConnectionEntity  # noqa: F401
    from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity  # noqa: F401
    from linkedout.education.entities.education_entity import EducationEntity  # noqa: F401
    from linkedout.experience.entities.experience_entity import ExperienceEntity  # noqa: F401
    from linkedout.profile_skill.entities.profile_skill_entity import ProfileSkillEntity  # noqa: F401
    from organization.entities.app_user_entity import AppUserEntity  # noqa: F401
    from organization.entities.bu_entity import BuEntity  # noqa: F401
    from organization.entities.tenant_entity import TenantEntity  # noqa: F401

    demo_tables = [
        TenantEntity.__table__,
        BuEntity.__table__,
        AppUserEntity.__table__,
        CompanyEntity.__table__,
        CrawledProfileEntity.__table__,
        ExperienceEntity.__table__,
        EducationEntity.__table__,
        ProfileSkillEntity.__table__,
        ConnectionEntity.__table__,
    ]

    engine = create_engine(db_url)
    Base.metadata.create_all(engine, tables=demo_tables)
    engine.dispose()
    print(f"Created {len(demo_tables)} tables from entity metadata")


def _insert_data(db_url: str) -> None:
    """Insert synthetic rows with pre-computed embeddings."""
    ts = _now_iso()
    today = _today_iso()

    # ── Org data (required for connection FKs) ──────────────────
    org_sql = (
        f"INSERT INTO tenant (id, name, created_at, updated_at, is_active, version) "
        f"VALUES ('{DEMO_TENANT_ID}', 'Demo Tenant', '{ts}', '{ts}', TRUE, 1);\n"
        f"INSERT INTO bu (id, tenant_id, name, created_at, updated_at, is_active, version) "
        f"VALUES ('{DEMO_BU_ID}', '{DEMO_TENANT_ID}', 'Demo BU', '{ts}', '{ts}', TRUE, 1);\n"
        f"INSERT INTO app_user (id, email, name, created_at, updated_at, is_active, version) "
        f"VALUES ('{DEMO_APP_USER_ID}', 'demo@example.com', 'Demo User', '{ts}', '{ts}', TRUE, 1);"
    )
    _psql(db_url, org_sql, "org data")

    # ── Companies ────────────────────────────────────────────────
    companies_sql_parts = []
    industries = [
        "AI/ML", "SaaS", "Developer Tools", "Fintech", "Healthcare",
        "Cloud Infrastructure", "Data Analytics", "Cybersecurity",
        "Robotics", "EdTech", "E-commerce", "Biotech",
        "Autonomous Vehicles", "Enterprise Software", "Social Media",
    ]
    cities = ["San Francisco", "New York", "Bengaluru", "London", "Berlin",
              "Seattle", "Austin", "Toronto", "Singapore", "Tel Aviv"]

    for i in range(1, NUM_COMPANIES + 1):
        companies_sql_parts.append(
            f"('co_demo_{i:03d}', 'Demo Company {i}', 'demo company {i}', "
            f"'https://linkedin.com/company/demo-co-{i}', "
            f"'democo{i}.example.com', '{industries[i % len(industries)]}', "
            f"{2010 + i % 15}, '{cities[i % len(cities)]}', 'US', "
            f"'{'51-200' if i <= 7 else '201-500'}', "
            f"'{'SMB' if i <= 7 else 'Mid-Market'}', "
            f"{i * 5}, '{ts}', '{ts}', TRUE)"
        )

    companies_sql = (
        "INSERT INTO company (id, canonical_name, normalized_name, linkedin_url, "
        "domain, industry, founded_year, hq_city, hq_country, "
        "employee_count_range, size_tier, network_connection_count, "
        "created_at, updated_at, is_active) VALUES\n"
        + ",\n".join(companies_sql_parts) + ";"
    )
    _psql(db_url, companies_sql, "companies")

    # ── Profiles ─────────────────────────────────────────────────
    # Profile 1 is the "system user" — founder/CTO composite
    roles = [
        ("Founder & CTO", "c-suite", "engineering"),
        ("Senior ML Engineer", "senior", "engineering"),
        ("Product Manager", "mid", "product"),
        ("Data Scientist", "mid", "data"),
        ("Staff Engineer", "senior", "engineering"),
        ("VP Engineering", "executive", "engineering"),
        ("ML Research Scientist", "senior", "engineering"),
        ("Senior Product Designer", "senior", "design"),
        ("DevOps Lead", "senior", "engineering"),
        ("Junior Software Engineer", "junior", "engineering"),
    ]
    profile_sql_parts = []
    for i in range(1, NUM_PROFILES + 1):
        title, seniority, area = roles[i - 1]
        co_idx = (i % NUM_COMPANIES) + 1
        embedding = _random_embedding()
        profile_sql_parts.append(
            f"('cp_demo_{i:03d}', 'https://linkedin.com/in/demo-person-{i}', "
            f"'demo-person-{i}', 'Demo{i}', 'Person{i}', 'Demo{i} Person{i}', "
            f"'{title} at Demo Company {co_idx}', "
            f"'Experienced {title.lower()} with a passion for building.', "
            f"'{cities[i % len(cities)]}', 'US', {500 + i * 50}, "
            f"'Demo Company {co_idx}', '{title}', 'co_demo_{co_idx:03d}', "
            f"'{seniority}', '{area}', 'demo', "
            f"{'TRUE' if i <= 5 else 'FALSE'}, "
            f"'{embedding}', '{ts}', '{ts}', TRUE)"
        )

    profiles_sql = (
        "INSERT INTO crawled_profile (id, linkedin_url, public_identifier, "
        "first_name, last_name, full_name, headline, about, "
        "location_city, location_country, connections_count, "
        "current_company_name, current_position, company_id, "
        "seniority_level, function_area, data_source, "
        "has_enriched_data, embedding_nomic, "
        "created_at, updated_at, is_active) VALUES\n"
        + ",\n".join(profile_sql_parts) + ";"
    )
    _psql(db_url, profiles_sql, "profiles")

    # ── Experiences ──────────────────────────────────────────────
    exp_sql_parts = []
    positions = [
        "Software Engineer", "Senior Software Engineer", "ML Engineer",
        "Product Manager", "Data Scientist", "Staff Engineer",
        "Tech Lead", "Engineering Manager", "Research Scientist",
        "DevOps Engineer",
    ]
    for i in range(1, NUM_EXPERIENCES + 1):
        cp_idx = ((i - 1) % NUM_PROFILES) + 1
        co_idx = ((i - 1) % NUM_COMPANIES) + 1
        pos = positions[i % len(positions)]
        start_year = 2015 + (i % 8)
        is_current = i % 5 == 0
        end_year = "NULL" if is_current else str(start_year + 2)
        exp_sql_parts.append(
            f"('exp_demo_{i:03d}', 'cp_demo_{cp_idx:03d}', '{pos}', "
            f"'Demo Company {co_idx}', 'co_demo_{co_idx:03d}', "
            f"{start_year}, {end_year}, {str(is_current).upper()}, "
            f"'{'senior' if i % 3 == 0 else 'mid'}', 'engineering', "
            f"'Built and maintained systems for demo project {i}.', "
            f"'{ts}', '{ts}', TRUE)"
        )

    exp_sql = (
        "INSERT INTO experience (id, crawled_profile_id, position, "
        "company_name, company_id, start_year, end_year, is_current, "
        "seniority_level, function_area, description, "
        "created_at, updated_at, is_active) VALUES\n"
        + ",\n".join(exp_sql_parts) + ";"
    )
    _psql(db_url, exp_sql, "experiences")

    # ── Education ────────────────────────────────────────────────
    edu_sql_parts = []
    schools = ["MIT", "Stanford", "IIT Bombay", "CMU", "UC Berkeley",
               "Georgia Tech", "Caltech", "Harvard", "Oxford", "ETH Zurich"]
    for i in range(1, NUM_EDUCATIONS + 1):
        cp_idx = ((i - 1) % NUM_PROFILES) + 1
        school = schools[i % len(schools)]
        degree = "MS" if i % 3 == 0 else "BS"
        field = "Computer Science" if i % 2 == 0 else "Electrical Engineering"
        edu_sql_parts.append(
            f"('edu_demo_{i:03d}', 'cp_demo_{cp_idx:03d}', '{school}', "
            f"'{degree}', '{field}', {2010 + i % 5}, {2014 + i % 5}, "
            f"'{ts}', '{ts}', TRUE)"
        )

    edu_sql = (
        "INSERT INTO education (id, crawled_profile_id, school_name, "
        "degree, field_of_study, start_year, end_year, "
        "created_at, updated_at, is_active) VALUES\n"
        + ",\n".join(edu_sql_parts) + ";"
    )
    _psql(db_url, edu_sql, "education")

    # ── Skills ───────────────────────────────────────────────────
    skill_sql_parts = []
    skill_names = [
        "Python", "Machine Learning", "PyTorch", "TensorFlow", "SQL",
        "Docker", "Kubernetes", "AWS", "Go", "Rust",
        "Data Engineering", "Product Strategy", "System Design",
        "NLP", "Computer Vision",
    ]
    for i in range(1, NUM_SKILLS + 1):
        cp_idx = ((i - 1) % NUM_PROFILES) + 1
        skill = skill_names[i % len(skill_names)]
        skill_sql_parts.append(
            f"('psk_demo_{i:03d}', 'cp_demo_{cp_idx:03d}', '{skill}', "
            f"{i * 3}, '{ts}', '{ts}', TRUE)"
        )

    skill_sql = (
        "INSERT INTO profile_skill (id, crawled_profile_id, skill_name, "
        "endorsement_count, created_at, updated_at, is_active) VALUES\n"
        + ",\n".join(skill_sql_parts) + ";"
    )
    _psql(db_url, skill_sql, "skills")

    # ── Connections ──────────────────────────────────────────────
    # Demo app user connected to all profiles.
    # Affinity sub-score columns are NOT NULL with Python-side defaults only,
    # so we must provide explicit values in raw SQL.
    conn_sql_parts = []
    conn_id = 0
    for i in range(1, NUM_PROFILES + 1):
        conn_id += 1
        affinity = round(1.0 - (i - 1) * 0.08, 2) if i <= 10 else 0.2
        conn_sql_parts.append(
            f"('conn_demo_{conn_id:03d}', "
            f"'{DEMO_TENANT_ID}', '{DEMO_BU_ID}', '{DEMO_APP_USER_ID}', "
            f"'cp_demo_{i:03d}', '{today}', "
            f"ARRAY['demo'], {affinity}, "
            f"0, 0, 0, 0, 0, 0, 0, "
            f"'{ts}', '{ts}', TRUE)"
        )

    conn_sql = (
        "INSERT INTO connection (id, tenant_id, bu_id, app_user_id, "
        "crawled_profile_id, connected_at, sources, affinity_score, "
        "affinity_source_count, affinity_recency, affinity_career_overlap, "
        "affinity_mutual_connections, affinity_external_contact, "
        "affinity_embedding_similarity, affinity_version, "
        "created_at, updated_at, is_active) VALUES\n"
        + ",\n".join(conn_sql_parts) + ";"
    )
    _psql(db_url, conn_sql, "connections")

    total = (
        3  # org records (tenant + bu + app_user)
        + NUM_COMPANIES + NUM_PROFILES + NUM_EXPERIENCES
        + NUM_EDUCATIONS + NUM_SKILLS + conn_id
    )
    print(f"Inserted {total} rows across 9 tables")
    print(f"  tenant: 1")
    print(f"  bu: 1")
    print(f"  app_user: 1")
    print(f"  companies: {NUM_COMPANIES}")
    print(f"  profiles: {NUM_PROFILES}")
    print(f"  experiences: {NUM_EXPERIENCES}")
    print(f"  educations: {NUM_EDUCATIONS}")
    print(f"  skills: {NUM_SKILLS}")
    print(f"  connections: {conn_id}")


if __name__ == "__main__":
    db_url = sys.argv[1] if len(sys.argv) > 1 else "postgresql://linkedout:linkedout@localhost:5432/linkedout"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    generate(base_db_url=db_url, output_path=out)
