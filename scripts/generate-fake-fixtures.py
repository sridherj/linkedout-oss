#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate fake fixture data for dev environments.

Replaces real LinkedIn profile data in backend/src/dev_tools/db/fixtures/
with obviously synthetic data that preserves referential integrity.

Usage:
    python scripts/generate-fake-fixtures.py
"""
from __future__ import annotations

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / 'backend' / 'src' / 'dev_tools' / 'db' / 'fixtures'

# ── Fake companies ────────────────────────────────────────────────────────────

COMPANIES = [
    {
        'id': 'co_fake_001',
        'canonical_name': 'Acme Corp',
        'normalized_name': 'acme corp',
        'linkedin_url': 'https://www.linkedin.com/company/acme-corp-example',
        'universal_name': 'acme-corp-example',
        'website': 'https://acme.example.com',
        'domain': 'acme.example.com',
        'industry': 'Software Development',
        'founded_year': 2010,
        'hq_city': 'San Francisco',
        'hq_country': 'United States',
        'employee_count_range': '1001-5000',
        'estimated_employee_count': 2500,
        'size_tier': 'mid',
        'network_connection_count': 42,
        'enrichment_sources': None,
    },
    {
        'id': 'co_fake_002',
        'canonical_name': 'Globex Industries',
        'normalized_name': 'globex industries',
        'linkedin_url': 'https://www.linkedin.com/company/globex-industries-example',
        'universal_name': 'globex-industries-example',
        'website': 'https://globex.example.com',
        'domain': 'globex.example.com',
        'industry': 'Information Technology & Services',
        'founded_year': 1998,
        'hq_city': 'New York',
        'hq_country': 'United States',
        'employee_count_range': '5001-10000',
        'estimated_employee_count': 7500,
        'size_tier': 'large',
        'network_connection_count': 15,
        'enrichment_sources': None,
    },
    {
        'id': 'co_fake_003',
        'canonical_name': 'Initech Solutions',
        'normalized_name': 'initech solutions',
        'linkedin_url': 'https://www.linkedin.com/company/initech-solutions-example',
        'universal_name': 'initech-solutions-example',
        'website': None,
        'domain': None,
        'industry': 'Financial Services',
        'founded_year': 2015,
        'hq_city': 'Austin',
        'hq_country': 'United States',
        'employee_count_range': '201-500',
        'estimated_employee_count': 350,
        'size_tier': 'small',
        'network_connection_count': 8,
        'enrichment_sources': None,
    },
]

# ── Fake profiles ─────────────────────────────────────────────────────────────

_PROFILE_TEMPLATES = [
    ('Alice', 'Anderson', 'Senior Software Engineer', 'co_fake_001', 'Acme Corp', 'San Francisco', 'CA', 'US'),
    ('Bob', 'Baker', 'Product Manager', 'co_fake_001', 'Acme Corp', 'San Francisco', 'CA', 'US'),
    ('Carol', 'Chen', 'Data Scientist', 'co_fake_002', 'Globex Industries', 'New York', 'NY', 'US'),
    ('David', 'Davis', 'Engineering Manager', 'co_fake_002', 'Globex Industries', 'New York', 'NY', 'US'),
    ('Eve', 'Evans', 'UX Designer', 'co_fake_001', 'Acme Corp', 'Austin', 'TX', 'US'),
    ('Frank', 'Foster', 'DevOps Engineer', 'co_fake_003', 'Initech Solutions', 'Austin', 'TX', 'US'),
    ('Grace', 'Green', 'Backend Engineer', 'co_fake_002', 'Globex Industries', 'Seattle', 'WA', 'US'),
    ('Henry', 'Hill', 'Technical Lead', 'co_fake_001', 'Acme Corp', 'San Francisco', 'CA', 'US'),
    ('Irene', 'Ingram', 'ML Engineer', 'co_fake_003', 'Initech Solutions', 'Boston', 'MA', 'US'),
    ('James', 'Jones', 'Frontend Engineer', 'co_fake_002', 'Globex Industries', 'Chicago', 'IL', 'US'),
    ('Karen', 'King', 'Solutions Architect', 'co_fake_001', 'Acme Corp', 'Austin', 'TX', 'US'),
    ('Leo', 'Lee', 'Security Engineer', 'co_fake_003', 'Initech Solutions', 'San Francisco', 'CA', 'US'),
    ('Maria', 'Martin', 'Product Designer', 'co_fake_002', 'Globex Industries', 'New York', 'NY', 'US'),
    ('Nick', 'Nelson', 'Platform Engineer', 'co_fake_001', 'Acme Corp', 'Seattle', 'WA', 'US'),
    ('Olivia', 'Owen', 'Data Engineer', 'co_fake_003', 'Initech Solutions', 'Austin', 'TX', 'US'),
    ('Paul', 'Parker', 'CTO', 'co_fake_002', 'Globex Industries', 'New York', 'NY', 'US'),
    ('Quinn', 'Quinn', 'Staff Engineer', 'co_fake_001', 'Acme Corp', 'San Francisco', 'CA', 'US'),
    ('Rachel', 'Roberts', 'Engineering Director', 'co_fake_003', 'Initech Solutions', 'Boston', 'MA', 'US'),
    ('Sam', 'Smith', 'Backend Engineer', 'co_fake_002', 'Globex Industries', 'Chicago', 'IL', 'US'),
    ('Tara', 'Taylor', 'VP Engineering', 'co_fake_001', 'Acme Corp', 'San Francisco', 'CA', 'US'),
]

PROFILES = []
for i, (first, last, title, co_id, co_name, city, state, country) in enumerate(_PROFILE_TEMPLATES, 1):
    slug = f'{first.lower()}-{last.lower()}-example'
    PROFILES.append({
        'id': f'cp_fake_{i:03d}',
        'linkedin_url': f'https://www.linkedin.com/in/{slug}',
        'public_identifier': slug,
        'first_name': first,
        'last_name': last,
        'full_name': f'{first} {last}',
        'headline': f'{title} at {co_name}',
        'about': f'Experienced {title.lower()} with a passion for building great products.',
        'location_city': city,
        'location_state': state,
        'location_country': 'United States',
        'location_country_code': country,
        'connections_count': 300 + i * 17,
        'follower_count': 310 + i * 15,
        'current_company_name': co_name,
        'current_position': title,
        'company_id': co_id,
        'seniority_level': 'senior' if 'Senior' in title or 'Staff' in title or 'Lead' in title else 'mid',
        'function_area': 'engineering',
        'has_enriched_data': True,
        'data_source': 'fixture',
        'profile_image_url': None,
        'open_to_work': False,
        'premium': i % 3 == 0,
    })

# ── Fake experiences ──────────────────────────────────────────────────────────

_POSITIONS = [
    ('Software Engineer', 'co_fake_001', 'Acme Corp'),
    ('Senior Engineer', 'co_fake_002', 'Globex Industries'),
    ('Junior Developer', 'co_fake_003', 'Initech Solutions'),
    ('Tech Lead', 'co_fake_001', 'Acme Corp'),
]

EXPERIENCES = []
exp_counter = 1
for profile in PROFILES:
    pid = profile['id']
    # Current role
    pos = _POSITIONS[exp_counter % len(_POSITIONS)]
    EXPERIENCES.append({
        'id': f'exp_fake_{exp_counter:04d}',
        'crawled_profile_id': pid,
        'position': profile['current_position'],
        'company_name': profile['current_company_name'],
        'company_id': profile['company_id'],
        'employment_type': 'Full-time',
        'start_year': 2022,
        'start_month': (exp_counter % 12) + 1,
        'end_year': None,
        'end_month': None,
        'is_current': True,
        'seniority_level': profile['seniority_level'],
        'function_area': 'engineering',
        'location': f"{profile['location_city']}, {profile['location_country']}",
    })
    exp_counter += 1
    # Previous role
    EXPERIENCES.append({
        'id': f'exp_fake_{exp_counter:04d}',
        'crawled_profile_id': pid,
        'position': pos[0],
        'company_name': pos[2],
        'company_id': pos[1],
        'employment_type': 'Full-time',
        'start_year': 2019,
        'start_month': (exp_counter % 12) + 1,
        'end_year': 2022,
        'end_month': (exp_counter % 12) + 1,
        'is_current': False,
        'seniority_level': 'mid',
        'function_area': 'engineering',
        'location': 'United States',
    })
    exp_counter += 1

# ── Fake educations ───────────────────────────────────────────────────────────

_SCHOOLS = [
    ('State University', 'Bachelor of Science', 'Computer Science'),
    ('Tech Institute', 'Master of Science', 'Software Engineering'),
    ('City College', 'Bachelor of Arts', 'Mathematics'),
    ('Online University', 'Bachelor of Science', 'Information Systems'),
]

EDUCATIONS = []
for i, profile in enumerate(PROFILES, 1):
    school = _SCHOOLS[i % len(_SCHOOLS)]
    EDUCATIONS.append({
        'id': f'edu_fake_{i:04d}',
        'crawled_profile_id': profile['id'],
        'school_name': school[0],
        'degree': school[1],
        'field_of_study': school[2],
        'start_year': 2012 + (i % 5),
        'end_year': 2016 + (i % 5),
    })

# ── Fake profile skills ───────────────────────────────────────────────────────

_SKILLS = [
    'Python', 'JavaScript', 'TypeScript', 'React', 'FastAPI',
    'PostgreSQL', 'Docker', 'Kubernetes', 'AWS', 'GCP',
    'Machine Learning', 'Data Analysis', 'System Design', 'Leadership', 'Agile',
]

PROFILE_SKILLS = []
skill_counter = 1
for profile in PROFILES:
    pid = profile['id']
    for j in range(3):
        skill = _SKILLS[(skill_counter + j) % len(_SKILLS)]
        PROFILE_SKILLS.append({
            'id': f'psk_fake_{skill_counter:04d}',
            'crawled_profile_id': pid,
            'skill_name': skill,
            'endorsement_count': (skill_counter % 20) * 3,
        })
        skill_counter += 1


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    files = {
        'companies.json': COMPANIES,
        'crawled_profiles.json': PROFILES,
        'experiences.json': EXPERIENCES,
        'educations.json': EDUCATIONS,
        'profile_skills.json': PROFILE_SKILLS,
    }

    for filename, data in files.items():
        path = FIXTURES_DIR / filename
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
        print(f'  wrote {len(data):4d} records → {path.relative_to(Path.cwd())}')

    print('\nDone. All fixture files contain synthetic data only.')


if __name__ == '__main__':
    main()
