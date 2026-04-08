# SPDX-License-Identifier: Apache-2.0
"""Apify JSONL Loader — loads LinkedIn profile data into PostgreSQL.

Reads Apify JSONL exports (one profile per line), deduplicates profiles by
linkedin_url, extracts companies, experience, education, and skills, then
bulk-inserts into the database in batches.

Usage:
    cd src && uv run python -m dev_tools.load_apify_profiles [--dry-run] [--batch-size 500]
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import click
from sqlalchemy.orm import Session

from linkedout.company.entities.company_entity import CompanyEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.education.entities.education_entity import EducationEntity
from linkedout.experience.entities.experience_entity import ExperienceEntity
from linkedout.profile_skill.entities.profile_skill_entity import ProfileSkillEntity
from dev_tools.db.fixed_data import SYSTEM_USER_ID
from shared.infra.db.db_session_manager import DbSessionType, db_session_manager
from shared.utils.company_matcher import CompanyMatcher
from shared.utils.date_parsing import parse_apify_date, parse_month_name
from shared.utils.linkedin_url import normalize_linkedin_url

# Default file paths (JSONL — one profile per line)
DATA_DIR = Path(__file__).resolve().parent.parent.parent / 'data'
FILE_NEWER = DATA_DIR / 'linkedin-profile1.jsonl'
FILE_OLDER = DATA_DIR / 'linkedin-profile2.jsonl'


# ─── JSONL Parser ──────────────────────────────────────────────────────────


def parse_jsonl_profiles(file_path: Path) -> tuple[list[dict], int]:
    """Parse a JSONL file into profile dicts (one JSON object per line).

    Returns (profiles, error_count).
    """
    profiles = []
    errors = 0

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict) and 'linkedinUrl' in obj:
                    profiles.append(obj)
            except (json.JSONDecodeError, UnicodeDecodeError):
                errors += 1

    return profiles, errors


# ─── Deduplication ──────────────────────────────────────────────────────────


def deduplicate_profiles(file2_profiles: list[dict], file1_profiles: list[dict]) -> dict[str, dict]:
    """Deduplicate profiles by normalized linkedin_url.

    File 2 (newer) is processed first — it wins on duplicates.
    Returns {normalized_url: profile_dict}.
    """
    seen: dict[str, dict] = {}

    for profiles in [file2_profiles, file1_profiles]:
        for profile in profiles:
            raw_url = profile.get('linkedinUrl', '')
            norm_url = normalize_linkedin_url(raw_url)
            if norm_url and norm_url not in seen:
                seen[norm_url] = profile

    return seen


# ─── Company Extraction ─────────────────────────────────────────────────────


def extract_companies(profiles: dict[str, dict]) -> CompanyMatcher:
    """Extract and deduplicate companies from all profiles.

    Sources: experience[] and currentPosition[] arrays.
    """
    matcher = CompanyMatcher()

    for profile in profiles.values():
        # From experience
        for exp in profile.get('experience', []) or []:
            name = exp.get('companyName')
            url = exp.get('companyLinkedinUrl')
            universal = exp.get('companyUniversalName')
            if name:
                matcher.match_or_create(name, linkedin_url=url, universal_name=universal)

        # From currentPosition
        for cp in profile.get('currentPosition', []) or []:
            name = cp.get('companyName')
            url = cp.get('companyLinkedinUrl')
            if name:
                matcher.match_or_create(name, linkedin_url=url)

    return matcher


# ─── Entity Builders ────────────────────────────────────────────────────────


def build_profile_entity(
    norm_url: str,
    profile: dict,
    company_id_map: dict[str, str],
    matcher: CompanyMatcher,
    now: datetime,
) -> CrawledProfileEntity:
    """Build a CrawledProfileEntity from an Apify profile dict."""
    location = profile.get('location') or {}
    parsed_loc = location.get('parsed') or {}

    # Determine current company
    current_positions = profile.get('currentPosition', []) or []
    current_company_name = current_positions[0].get('companyName') if current_positions else None
    current_position_title = None
    if current_positions:
        # Use headline as current_position if available
        current_position_title = profile.get('headline')

    # Resolve company_id for current company
    company_id = None
    if current_company_name:
        canonical = matcher.match_or_create(current_company_name)
        if canonical:
            company_id = company_id_map.get(canonical)

    first_name = profile.get('firstName') or None
    last_name = profile.get('lastName') or None
    parts = [p for p in [first_name, last_name] if p]
    full_name = ' '.join(parts) if parts else None

    # Store raw profile as JSON string (strip NUL bytes — PostgreSQL rejects them)
    try:
        raw_json = json.dumps(profile, ensure_ascii=False, default=str).replace('\x00', '')
    except (TypeError, ValueError):
        raw_json = None

    return CrawledProfileEntity(
        linkedin_url=norm_url,
        public_identifier=profile.get('publicIdentifier'),
        first_name=first_name or None,
        last_name=last_name or None,
        full_name=full_name,
        headline=profile.get('headline'),
        about=profile.get('about'),
        location_city=parsed_loc.get('city'),
        location_state=parsed_loc.get('state'),
        location_country=parsed_loc.get('country'),
        location_country_code=parsed_loc.get('countryCode') or location.get('countryCode'),
        location_raw=location.get('linkedinText'),
        connections_count=profile.get('connectionsCount'),
        follower_count=profile.get('followerCount'),
        open_to_work=profile.get('openToWork'),
        premium=profile.get('premium'),
        current_company_name=current_company_name,
        current_position=current_position_title,
        company_id=company_id,
        data_source='apify',
        has_enriched_data=True,
        last_crawled_at=now,
        raw_profile=raw_json,
    )


def build_experience_entities(
    profile_id: str,
    profile: dict,
    company_id_map: dict[str, str],
    matcher: CompanyMatcher,
) -> list[ExperienceEntity]:
    """Build ExperienceEntity rows from a profile's experience array."""
    entities = []
    seen_keys: set[tuple] = set()

    for exp in profile.get('experience', []) or []:
        company_name = exp.get('companyName')

        start_obj = exp.get('startDate') or {}
        end_obj = exp.get('endDate') or {}

        start_year = start_obj.get('year')
        start_month_text = start_obj.get('month')
        start_month = parse_month_name(str(start_month_text)) if start_month_text else None

        end_year = end_obj.get('year')
        end_month_text = end_obj.get('month')
        end_month = parse_month_name(str(end_month_text)) if end_month_text else None

        end_text = end_obj.get('text', '')
        is_current = isinstance(end_text, str) and end_text.strip().lower() == 'present'

        # Deduplicate within profile
        dedup_key = (profile_id, company_name, exp.get('position'), start_year, start_month)
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        # Resolve company_id
        company_id = None
        if company_name:
            canonical = matcher.match_or_create(
                company_name,
                linkedin_url=exp.get('companyLinkedinUrl'),
                universal_name=exp.get('companyUniversalName'),
            )
            if canonical:
                company_id = company_id_map.get(canonical)

        start_date = parse_apify_date(start_obj)
        end_date = parse_apify_date(end_obj)

        try:
            raw_json = json.dumps(exp, ensure_ascii=False, default=str).replace('\x00', '')
        except (TypeError, ValueError):
            raw_json = None

        entities.append(ExperienceEntity(
            crawled_profile_id=profile_id,
            position=exp.get('position'),
            company_name=company_name,
            company_id=company_id,
            company_linkedin_url=exp.get('companyLinkedinUrl'),
            employment_type=exp.get('employmentType'),
            start_date=start_date,
            start_year=start_year if isinstance(start_year, int) else None,
            start_month=start_month,
            end_date=end_date,
            end_year=end_year if isinstance(end_year, int) else None,
            end_month=end_month,
            end_date_text=end_text if end_text else None,
            is_current=is_current if is_current else None,
            location=exp.get('location'),
            description=exp.get('description'),
            raw_experience=raw_json,
        ))

    return entities


def build_education_entities(profile_id: str, profile: dict) -> list[EducationEntity]:
    """Build EducationEntity rows from a profile's education array."""
    entities = []

    for edu in profile.get('education', []) or []:
        start_obj = edu.get('startDate') or {}
        end_obj = edu.get('endDate') or {}

        try:
            raw_json = json.dumps(edu, ensure_ascii=False, default=str).replace('\x00', '')
        except (TypeError, ValueError):
            raw_json = None

        entities.append(EducationEntity(
            crawled_profile_id=profile_id,
            school_name=edu.get('schoolName'),
            school_linkedin_url=edu.get('schoolLinkedinUrl'),
            degree=edu.get('degree'),
            field_of_study=edu.get('fieldOfStudy'),
            start_year=start_obj.get('year') if isinstance(start_obj.get('year'), int) else None,
            end_year=end_obj.get('year') if isinstance(end_obj.get('year'), int) else None,
            description=edu.get('description'),
            raw_education=raw_json,
        ))

    return entities


def build_skill_entities(profile_id: str, profile: dict) -> list[ProfileSkillEntity]:
    """Build ProfileSkillEntity rows from a profile's skills array."""
    entities = []
    seen_names: set[str] = set()

    for skill in profile.get('skills', []) or []:
        name = skill.get('name')
        if not name or not name.strip():
            continue

        name = name.strip()

        # Truncate to 255 chars (column limit) before dedup check
        if len(name) > 255:
            name = name[:255]

        if name in seen_names:
            continue
        seen_names.add(name)

        entities.append(ProfileSkillEntity(
            crawled_profile_id=profile_id,
            skill_name=name,
            endorsement_count=0,
        ))

    return entities


# ─── Database Operations ────────────────────────────────────────────────────


def insert_companies(session: Session, matcher: CompanyMatcher) -> dict[str, str]:
    """Insert all companies and return {canonical_name: entity_id} map."""
    company_id_map: dict[str, str] = {}
    companies = matcher.get_all_companies()

    for company_data in companies:
        entity = CompanyEntity(
            canonical_name=company_data['canonical_name'],
            normalized_name=company_data['normalized_name'],
            linkedin_url=company_data.get('linkedin_url'),
            universal_name=company_data.get('universal_name'),
        )
        session.add(entity)
        session.flush()
        company_id_map[company_data['canonical_name']] = entity.id

    return company_id_map


def load_profiles_batch(
    session: Session,
    batch: list[tuple[str, dict]],
    company_id_map: dict[str, str],
    matcher: CompanyMatcher,
    now: datetime,
) -> dict[str, int]:
    """Load a batch of profiles with their relational data.

    Returns counts: {profiles, experiences, educations, skills, errors}.
    """
    counts = {'profiles': 0, 'experiences': 0, 'educations': 0, 'skills': 0, 'errors': 0}

    for norm_url, profile in batch:
        # Use savepoint so a single profile error doesn't abort the whole batch
        savepoint = session.begin_nested()
        try:
            # Create profile
            profile_entity = build_profile_entity(norm_url, profile, company_id_map, matcher, now)
            session.add(profile_entity)
            session.flush()  # Get the ID

            profile_id = profile_entity.id

            # Experience
            exp_entities = build_experience_entities(profile_id, profile, company_id_map, matcher)
            for e in exp_entities:
                session.add(e)
            counts['experiences'] += len(exp_entities)

            # Education
            edu_entities = build_education_entities(profile_id, profile)
            for e in edu_entities:
                session.add(e)
            counts['educations'] += len(edu_entities)

            # Skills
            skill_entities = build_skill_entities(profile_id, profile)
            for e in skill_entities:
                session.add(e)
            counts['skills'] += len(skill_entities)

            savepoint.commit()
            counts['profiles'] += 1

        except Exception as e:
            savepoint.rollback()
            counts['errors'] += 1
            click.echo(f'  Error on profile {norm_url}: {e}', err=True)

    return counts


# ─── Main ───────────────────────────────────────────────────────────────────


@click.command()
@click.option('--dry-run', is_flag=True, help='Parse and report only, do not write to DB')
@click.option('--batch-size', default=500, type=int, help='Profiles per commit batch')
@click.option('--newer', default=str(FILE_NEWER), help='Path to newer JSONL file (wins on duplicates)')
@click.option('--older', default=str(FILE_OLDER), help='Path to older JSONL file')
def main(dry_run: bool, batch_size: int, newer: str, older: str):
    """Load Apify LinkedIn profile data into PostgreSQL."""
    start_time = time.time()

    newer_path = Path(newer)
    older_path = Path(older)

    # Validate files exist
    for p in [newer_path, older_path]:
        if not p.exists():
            click.echo(f'ERROR: File not found: {p}', err=True)
            sys.exit(1)

    # Step 1: Parse both JSONL files (newer first — it wins on duplicates)
    click.echo(f'Parsing {newer_path.name}...')
    newer_profiles, errors_newer = parse_jsonl_profiles(newer_path)
    click.echo(f'  -> {len(newer_profiles)} profiles, {errors_newer} errors')

    click.echo(f'Parsing {older_path.name}...')
    older_profiles, errors_older = parse_jsonl_profiles(older_path)
    click.echo(f'  -> {len(older_profiles)} profiles, {errors_older} errors')

    total_errors = errors_newer + errors_older

    # Step 2: Deduplicate
    click.echo('Deduplicating profiles...')
    unique_profiles = deduplicate_profiles(newer_profiles, older_profiles)
    click.echo(f'  -> {len(unique_profiles)} unique profiles')

    # Step 3: Extract companies
    click.echo('Extracting companies...')
    matcher = extract_companies(unique_profiles)
    click.echo(f'  -> {len(matcher)} unique companies')

    if dry_run:
        click.echo('\n--- DRY RUN COMPLETE ---')
        click.echo(f'Would create: {len(matcher)} companies, {len(unique_profiles)} profiles')
        elapsed = time.time() - start_time
        click.echo(f'Elapsed: {elapsed:.1f}s')
        return

    # Step 4: Insert into database
    click.echo('\nInserting companies...')
    with db_session_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
        company_id_map = insert_companies(session, matcher)
        click.echo(f'  -> {len(company_id_map)} companies inserted')

    # Step 5: Load profiles in batches
    click.echo(f'\nLoading profiles (batch size: {batch_size})...')
    now = datetime.now(timezone.utc)
    items = list(unique_profiles.items())
    total = len(items)
    totals = {'profiles': 0, 'experiences': 0, 'educations': 0, 'skills': 0, 'errors': 0}
    batch_num = 0

    for i in range(0, total, batch_size):
        batch = items[i:i + batch_size]
        batch_num += 1

        with db_session_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
            counts = load_profiles_batch(session, batch, company_id_map, matcher, now)

        for k in totals:
            totals[k] += counts[k]

        progress = min(i + batch_size, total)
        click.echo(f'  Batch {batch_num}: {progress}/{total} profiles ({totals["profiles"]} ok, {totals["errors"]} errors)')

    # Step 6: Summary
    elapsed = time.time() - start_time
    click.echo('\n=== LOAD COMPLETE ===')
    click.echo(f'Profiles:    {totals["profiles"]:>8,}')
    click.echo(f'Companies:   {len(company_id_map):>8,}')
    click.echo(f'Experiences: {totals["experiences"]:>8,}')
    click.echo(f'Educations:  {totals["educations"]:>8,}')
    click.echo(f'Skills:      {totals["skills"]:>8,}')
    click.echo(f'Errors:      {totals["errors"]:>8,}')
    click.echo(f'Parse errs:  {total_errors:>8,}')
    click.echo(f'Elapsed:     {elapsed:>7.1f}s')


if __name__ == '__main__':
    main()
