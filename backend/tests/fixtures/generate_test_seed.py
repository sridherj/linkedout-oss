# SPDX-License-Identifier: Apache-2.0
"""Generate a small SQLite test fixture for seed data pipeline tests.

Creates ``test-seed-core.sqlite`` with ~10 rows per table using synthetic data.
Runnable standalone to regenerate the fixture if the schema changes::

    cd backend/tests/fixtures
    python generate_test_seed.py
"""
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def _create_tables(cursor: sqlite3.Cursor) -> None:
    """Create all 10 seed tables + _metadata in the SQLite file."""

    cursor.execute("""
        CREATE TABLE company (
            id TEXT PRIMARY KEY,
            canonical_name TEXT NOT NULL UNIQUE,
            normalized_name TEXT NOT NULL,
            linkedin_url TEXT,
            universal_name TEXT,
            website TEXT,
            domain TEXT,
            industry TEXT,
            founded_year INTEGER,
            hq_city TEXT,
            hq_country TEXT,
            employee_count_range TEXT,
            estimated_employee_count INTEGER,
            size_tier TEXT,
            network_connection_count INTEGER NOT NULL DEFAULT 0,
            parent_company_id TEXT,
            enrichment_sources TEXT,
            enriched_at TEXT,
            pdl_id TEXT,
            wikidata_id TEXT,
            created_at TEXT,
            updated_at TEXT,
            deleted_at TEXT,
            created_by TEXT,
            updated_by TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE company_alias (
            id TEXT PRIMARY KEY,
            alias_name TEXT NOT NULL,
            company_id TEXT NOT NULL,
            source TEXT,
            created_at TEXT,
            updated_at TEXT,
            deleted_at TEXT,
            created_by TEXT,
            updated_by TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE role_alias (
            id TEXT PRIMARY KEY,
            alias_title TEXT NOT NULL UNIQUE,
            canonical_title TEXT NOT NULL,
            seniority_level TEXT,
            function_area TEXT,
            created_at TEXT,
            updated_at TEXT,
            deleted_at TEXT,
            created_by TEXT,
            updated_by TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE funding_round (
            id TEXT PRIMARY KEY,
            company_id TEXT NOT NULL,
            round_type TEXT NOT NULL,
            announced_on TEXT,
            amount_usd INTEGER,
            lead_investors TEXT,
            all_investors TEXT,
            source_url TEXT,
            confidence INTEGER DEFAULT 5,
            created_at TEXT,
            updated_at TEXT,
            deleted_at TEXT,
            created_by TEXT,
            updated_by TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE startup_tracking (
            id TEXT PRIMARY KEY,
            company_id TEXT NOT NULL UNIQUE,
            watching INTEGER DEFAULT 0,
            description TEXT,
            vertical TEXT,
            sub_category TEXT,
            funding_stage TEXT,
            total_raised_usd INTEGER,
            last_funding_date TEXT,
            round_count INTEGER DEFAULT 0,
            estimated_arr_usd INTEGER,
            arr_signal_date TEXT,
            arr_confidence INTEGER,
            created_at TEXT,
            updated_at TEXT,
            deleted_at TEXT,
            created_by TEXT,
            updated_by TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE growth_signal (
            id TEXT PRIMARY KEY,
            company_id TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            signal_date TEXT NOT NULL,
            value_numeric INTEGER,
            value_text TEXT,
            source_url TEXT,
            confidence INTEGER DEFAULT 5,
            created_at TEXT,
            updated_at TEXT,
            deleted_at TEXT,
            created_by TEXT,
            updated_by TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE crawled_profile (
            id TEXT PRIMARY KEY,
            linkedin_url TEXT NOT NULL UNIQUE,
            public_identifier TEXT,
            first_name TEXT,
            last_name TEXT,
            full_name TEXT,
            headline TEXT,
            about TEXT,
            location_city TEXT,
            location_state TEXT,
            location_country TEXT,
            location_country_code TEXT,
            location_raw TEXT,
            connections_count INTEGER,
            follower_count INTEGER,
            open_to_work INTEGER,
            premium INTEGER,
            current_company_name TEXT,
            current_position TEXT,
            company_id TEXT,
            seniority_level TEXT,
            function_area TEXT,
            data_source TEXT NOT NULL,
            has_enriched_data INTEGER NOT NULL DEFAULT 0,
            last_crawled_at TEXT,
            profile_image_url TEXT,
            notes TEXT,
            raw_profile TEXT,
            source_app_user_id TEXT,
            created_at TEXT,
            updated_at TEXT,
            deleted_at TEXT,
            created_by TEXT,
            updated_by TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE experience (
            id TEXT PRIMARY KEY,
            crawled_profile_id TEXT NOT NULL,
            position TEXT,
            position_normalized TEXT,
            company_name TEXT,
            company_id TEXT,
            company_linkedin_url TEXT,
            employment_type TEXT,
            start_date TEXT,
            start_year INTEGER,
            start_month INTEGER,
            end_date TEXT,
            end_year INTEGER,
            end_month INTEGER,
            end_date_text TEXT,
            is_current INTEGER,
            seniority_level TEXT,
            function_area TEXT,
            location TEXT,
            description TEXT,
            raw_experience TEXT,
            created_at TEXT,
            updated_at TEXT,
            deleted_at TEXT,
            created_by TEXT,
            updated_by TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE education (
            id TEXT PRIMARY KEY,
            crawled_profile_id TEXT NOT NULL,
            school_name TEXT,
            school_linkedin_url TEXT,
            degree TEXT,
            field_of_study TEXT,
            start_year INTEGER,
            end_year INTEGER,
            description TEXT,
            raw_education TEXT,
            created_at TEXT,
            updated_at TEXT,
            deleted_at TEXT,
            created_by TEXT,
            updated_by TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE profile_skill (
            id TEXT PRIMARY KEY,
            crawled_profile_id TEXT NOT NULL,
            skill_name TEXT NOT NULL,
            endorsement_count INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            deleted_at TEXT,
            created_by TEXT,
            updated_by TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE _metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')


def _populate(cursor: sqlite3.Cursor) -> dict[str, int]:
    """Insert synthetic rows into all tables. Returns table_counts."""
    ts = _now_iso()
    base = dict(created_at=ts, updated_at=ts, deleted_at=None,
                created_by=None, updated_by=None, active=1, version=1)

    # --- Companies (10) ---
    companies = []
    industries = ['Technology', 'Finance', 'Healthcare', 'Education',
                  'Retail', 'Energy', 'Media', 'SaaS', 'AI', 'Biotech']
    for i in range(1, 11):
        companies.append({
            'id': f'co_test_{i:03d}',
            'canonical_name': f'Test Company {i}',
            'normalized_name': f'test company {i}',
            'linkedin_url': f'https://linkedin.com/company/test-co-{i}',
            'universal_name': f'test-co-{i}',
            'website': f'https://testco{i}.example.com',
            'domain': f'testco{i}.example.com',
            'industry': industries[i - 1],
            'founded_year': 2000 + i,
            'hq_city': 'San Francisco' if i <= 5 else 'New York',
            'hq_country': 'US',
            'employee_count_range': '51-200' if i <= 5 else '201-500',
            'estimated_employee_count': 100 * i,
            'size_tier': 'SMB' if i <= 5 else 'Mid-Market',
            'network_connection_count': i * 3,
            'parent_company_id': None,
            'enrichment_sources': json.dumps(['linkedin', 'pdl']) if i <= 5 else None,
            'enriched_at': ts if i <= 5 else None,
            'pdl_id': f'pdl_{i}' if i <= 3 else None,
            'wikidata_id': f'Q{1000 + i}' if i <= 2 else None,
            **base,
        })

    cols = list(companies[0].keys())
    placeholders = ', '.join(['?'] * len(cols))
    cursor.executemany(
        f"INSERT INTO company ({', '.join(cols)}) VALUES ({placeholders})",
        [tuple(c[k] for k in cols) for c in companies],
    )

    # --- Company Aliases (15) ---
    aliases = []
    for i in range(1, 16):
        co_idx = ((i - 1) % 10) + 1
        aliases.append({
            'id': f'ca_test_{i:03d}',
            'alias_name': f'TC{co_idx} Alias {i}',
            'company_id': f'co_test_{co_idx:03d}',
            'source': 'linkedin' if i % 2 == 0 else 'manual',
            **base,
        })

    cols = list(aliases[0].keys())
    placeholders = ', '.join(['?'] * len(cols))
    cursor.executemany(
        f"INSERT INTO company_alias ({', '.join(cols)}) VALUES ({placeholders})",
        [tuple(a[k] for k in cols) for a in aliases],
    )

    # --- Role Aliases (10) ---
    role_aliases = []
    titles = [
        ('SWE', 'Software Engineer', 'mid', 'engineering'),
        ('Sr SWE', 'Senior Software Engineer', 'senior', 'engineering'),
        ('PM', 'Product Manager', 'mid', 'product'),
        ('Sr PM', 'Senior Product Manager', 'senior', 'product'),
        ('DS', 'Data Scientist', 'mid', 'data'),
        ('ML Eng', 'Machine Learning Engineer', 'mid', 'engineering'),
        ('VP Eng', 'VP of Engineering', 'executive', 'engineering'),
        ('CTO', 'Chief Technology Officer', 'c-suite', 'engineering'),
        ('Designer', 'Product Designer', 'mid', 'design'),
        ('DevOps', 'DevOps Engineer', 'mid', 'engineering'),
    ]
    for i, (alias, canonical, seniority, area) in enumerate(titles, 1):
        role_aliases.append({
            'id': f'ra_test_{i:03d}',
            'alias_title': alias,
            'canonical_title': canonical,
            'seniority_level': seniority,
            'function_area': area,
            **base,
        })

    cols = list(role_aliases[0].keys())
    placeholders = ', '.join(['?'] * len(cols))
    cursor.executemany(
        f"INSERT INTO role_alias ({', '.join(cols)}) VALUES ({placeholders})",
        [tuple(r[k] for k in cols) for r in role_aliases],
    )

    # --- Funding Rounds (8 across 4 companies) ---
    funding = []
    rounds_data = [
        ('co_test_001', 'Seed', '2020-03-15', 2_000_000, ['Sequoia'], ['Sequoia', 'YC']),
        ('co_test_001', 'Series A', '2022-01-10', 15_000_000, ['a16z'], ['a16z', 'Sequoia']),
        ('co_test_002', 'Seed', '2019-06-01', 1_500_000, ['Founders Fund'], ['Founders Fund']),
        ('co_test_002', 'Series A', '2021-09-20', 12_000_000, ['Benchmark'], ['Benchmark', 'Founders Fund']),
        ('co_test_003', 'Seed', '2021-01-05', 3_000_000, ['Greylock'], ['Greylock']),
        ('co_test_003', 'Series A', '2023-04-15', 20_000_000, ['Accel'], ['Accel', 'Greylock']),
        ('co_test_004', 'Seed', '2022-07-01', 5_000_000, ['Index'], ['Index', 'SV Angel']),
        ('co_test_004', 'Series A', '2024-02-28', 25_000_000, ['Tiger Global'], ['Tiger Global', 'Index']),
    ]
    for i, (co_id, rtype, date, amount, lead, all_inv) in enumerate(rounds_data, 1):
        funding.append({
            'id': f'fr_test_{i:03d}',
            'company_id': co_id,
            'round_type': rtype,
            'announced_on': date,
            'amount_usd': amount,
            'lead_investors': json.dumps(lead),
            'all_investors': json.dumps(all_inv),
            'source_url': f'https://crunchbase.com/round/{i}',
            'confidence': 8,
            **base,
        })

    cols = list(funding[0].keys())
    placeholders = ', '.join(['?'] * len(cols))
    cursor.executemany(
        f"INSERT INTO funding_round ({', '.join(cols)}) VALUES ({placeholders})",
        [tuple(f[k] for k in cols) for f in funding],
    )

    # --- Startup Tracking (5) ---
    tracking = []
    for i in range(1, 6):
        tracking.append({
            'id': f'st_test_{i:03d}',
            'company_id': f'co_test_{i:03d}',
            'watching': 1 if i <= 3 else 0,
            'description': f'Tracking test company {i}',
            'vertical': 'AI Agents' if i <= 2 else 'SaaS',
            'sub_category': 'Developer Tools',
            'funding_stage': 'Series A' if i <= 3 else 'Seed',
            'total_raised_usd': 10_000_000 * i,
            'last_funding_date': f'2024-0{i}-01',
            'round_count': 2 if i <= 3 else 1,
            'estimated_arr_usd': 1_000_000 * i if i <= 3 else None,
            'arr_signal_date': '2024-06-01' if i <= 3 else None,
            'arr_confidence': 7 if i <= 3 else None,
            **base,
        })

    cols = list(tracking[0].keys())
    placeholders = ', '.join(['?'] * len(cols))
    cursor.executemany(
        f"INSERT INTO startup_tracking ({', '.join(cols)}) VALUES ({placeholders})",
        [tuple(t[k] for k in cols) for t in tracking],
    )

    # --- Growth Signals (12) ---
    signals = []
    for i in range(1, 13):
        co_idx = ((i - 1) % 5) + 1
        signals.append({
            'id': f'gs_test_{i:03d}',
            'company_id': f'co_test_{co_idx:03d}',
            'signal_type': 'headcount' if i % 2 == 0 else 'revenue',
            'signal_date': f'2024-{((i - 1) % 12) + 1:02d}-15',
            'value_numeric': 100_000 * i,
            'value_text': f'${100 * i}K' if i % 2 != 0 else f'{10 * i} employees',
            'source_url': f'https://example.com/signal/{i}',
            'confidence': min(i, 10),
            **base,
        })

    cols = list(signals[0].keys())
    placeholders = ', '.join(['?'] * len(cols))
    cursor.executemany(
        f"INSERT INTO growth_signal ({', '.join(cols)}) VALUES ({placeholders})",
        [tuple(s[k] for k in cols) for s in signals],
    )

    # --- Crawled Profiles (20) ---
    profiles = []
    for i in range(1, 21):
        co_idx = ((i - 1) % 10) + 1
        profiles.append({
            'id': f'cp_test_{i:03d}',
            'linkedin_url': f'https://linkedin.com/in/test-person-{i}',
            'public_identifier': f'test-person-{i}',
            'first_name': f'First{i}',
            'last_name': f'Last{i}',
            'full_name': f'First{i} Last{i}',
            'headline': f'Engineer at Test Company {co_idx}',
            'about': f'Experienced professional #{i}',
            'location_city': 'San Francisco' if i <= 10 else 'New York',
            'location_state': 'CA' if i <= 10 else 'NY',
            'location_country': 'United States',
            'location_country_code': 'US',
            'location_raw': 'San Francisco Bay Area' if i <= 10 else 'New York City',
            'connections_count': 500 + i * 10,
            'follower_count': 100 + i * 5,
            'open_to_work': 1 if i % 5 == 0 else 0,
            'premium': 1 if i % 3 == 0 else 0,
            'current_company_name': f'Test Company {co_idx}',
            'current_position': f'Software Engineer {i}',
            'company_id': f'co_test_{co_idx:03d}',
            'seniority_level': 'senior' if i % 3 == 0 else 'mid',
            'function_area': 'engineering',
            'data_source': 'extension',
            'has_enriched_data': 1 if i <= 5 else 0,
            'last_crawled_at': ts,
            'profile_image_url': f'https://example.com/photos/{i}.jpg',
            'notes': None,
            'raw_profile': None,
            'source_app_user_id': None,
            **base,
        })

    cols = list(profiles[0].keys())
    placeholders = ', '.join(['?'] * len(cols))
    cursor.executemany(
        f"INSERT INTO crawled_profile ({', '.join(cols)}) VALUES ({placeholders})",
        [tuple(p[k] for k in cols) for p in profiles],
    )

    # --- Experience (40) ---
    experiences = []
    for i in range(1, 41):
        cp_idx = ((i - 1) % 20) + 1
        co_idx = ((i - 1) % 10) + 1
        experiences.append({
            'id': f'exp_test_{i:03d}',
            'crawled_profile_id': f'cp_test_{cp_idx:03d}',
            'position': f'Engineer Level {(i % 5) + 1}',
            'position_normalized': 'Software Engineer',
            'company_name': f'Test Company {co_idx}',
            'company_id': f'co_test_{co_idx:03d}',
            'company_linkedin_url': f'https://linkedin.com/company/test-co-{co_idx}',
            'employment_type': 'full-time',
            'start_date': f'{2018 + (i % 5)}-01-01',
            'start_year': 2018 + (i % 5),
            'start_month': 1,
            'end_date': None if i % 4 == 0 else f'{2022 + (i % 3)}-06-15',
            'end_year': None if i % 4 == 0 else 2022 + (i % 3),
            'end_month': None if i % 4 == 0 else 6,
            'end_date_text': 'Present' if i % 4 == 0 else None,
            'is_current': 1 if i % 4 == 0 else 0,
            'seniority_level': 'senior' if i % 3 == 0 else 'mid',
            'function_area': 'engineering',
            'location': 'San Francisco, CA',
            'description': f'Built systems for test project {i}',
            'raw_experience': None,
            **base,
        })

    cols = list(experiences[0].keys())
    placeholders = ', '.join(['?'] * len(cols))
    cursor.executemany(
        f"INSERT INTO experience ({', '.join(cols)}) VALUES ({placeholders})",
        [tuple(e[k] for k in cols) for e in experiences],
    )

    # --- Education (25) ---
    educations = []
    schools = ['MIT', 'Stanford', 'UC Berkeley', 'CMU', 'Harvard',
               'Yale', 'Princeton', 'Caltech', 'Georgia Tech', 'UW']
    for i in range(1, 26):
        cp_idx = ((i - 1) % 20) + 1
        educations.append({
            'id': f'edu_test_{i:03d}',
            'crawled_profile_id': f'cp_test_{cp_idx:03d}',
            'school_name': schools[(i - 1) % len(schools)],
            'school_linkedin_url': f'https://linkedin.com/school/{schools[(i - 1) % len(schools)].lower().replace(" ", "-")}',
            'degree': 'BS' if i % 3 != 0 else 'MS',
            'field_of_study': 'Computer Science' if i % 2 == 0 else 'Electrical Engineering',
            'start_year': 2010 + (i % 5),
            'end_year': 2014 + (i % 5),
            'description': f'Studied at {schools[(i - 1) % len(schools)]}',
            'raw_education': None,
            **base,
        })

    cols = list(educations[0].keys())
    placeholders = ', '.join(['?'] * len(cols))
    cursor.executemany(
        f"INSERT INTO education ({', '.join(cols)}) VALUES ({placeholders})",
        [tuple(e[k] for k in cols) for e in educations],
    )

    # --- Profile Skills (30) ---
    skills = []
    skill_names = ['Python', 'Java', 'JavaScript', 'Go', 'Rust',
                   'SQL', 'Docker', 'Kubernetes', 'AWS', 'GCP',
                   'Machine Learning', 'Data Science', 'React', 'Node.js', 'TypeScript']
    for i in range(1, 31):
        cp_idx = ((i - 1) % 20) + 1
        skills.append({
            'id': f'psk_test_{i:03d}',
            'crawled_profile_id': f'cp_test_{cp_idx:03d}',
            'skill_name': skill_names[(i - 1) % len(skill_names)],
            'endorsement_count': i * 2,
            **base,
        })

    cols = list(skills[0].keys())
    placeholders = ', '.join(['?'] * len(cols))
    cursor.executemany(
        f"INSERT INTO profile_skill ({', '.join(cols)}) VALUES ({placeholders})",
        [tuple(s[k] for k in cols) for s in skills],
    )

    return {
        'company': len(companies),
        'company_alias': len(aliases),
        'role_alias': len(role_aliases),
        'funding_round': len(funding),
        'startup_tracking': len(tracking),
        'growth_signal': len(signals),
        'crawled_profile': len(profiles),
        'experience': len(experiences),
        'education': len(educations),
        'profile_skill': len(skills),
    }


def generate(output_path: Path | None = None) -> Path:
    """Generate the test fixture SQLite file.

    Args:
        output_path: Where to write the file. Defaults to
            ``test-seed-core.sqlite`` in the same directory as this script.

    Returns:
        Path to the generated file.
    """
    if output_path is None:
        output_path = Path(__file__).parent / 'test-seed-core.sqlite'

    if output_path.exists():
        output_path.unlink()

    conn = sqlite3.connect(str(output_path))
    cursor = conn.cursor()

    cursor.execute('PRAGMA journal_mode=DELETE')
    cursor.execute('PRAGMA synchronous=FULL')

    _create_tables(cursor)
    table_counts = _populate(cursor)

    # Write _metadata
    ts = _now_iso()
    cursor.executemany('INSERT INTO _metadata (key, value) VALUES (?, ?)', [
        ('version', '0.0.1-test'),
        ('created_at', ts),
        ('source_db_hash', 'test_fixture'),
        ('table_counts', json.dumps(table_counts, sort_keys=True)),
    ])

    conn.commit()
    cursor.execute('VACUUM')
    conn.close()

    print(f'Generated: {output_path}')
    print(f'Tables: {len(table_counts)}')
    for table, count in table_counts.items():
        print(f'  {table}: {count} rows')
    total = sum(table_counts.values())
    print(f'  Total: {total} rows')

    return output_path


if __name__ == '__main__':
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    generate(path)
