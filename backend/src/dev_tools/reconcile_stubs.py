# SPDX-License-Identifier: Apache-2.0
"""Reconcile stub connections with LinkedIn connections.

Post-import reconciliation pass that merges Google Contact stubs into LinkedIn
connections using first-name uniqueness (Tier 1) and company-hint disambiguation
(Tier 2). Produces a JSON reconciliation log for rollback.

Can run as one-time fix or be triggered after each Google Contacts import.
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone

import click
from sqlalchemy import func, select

from linkedout.company.entities.company_entity import CompanyEntity
from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.experience.entities.experience_entity import ExperienceEntity
from linkedout.import_pipeline.merge import merge_stub_into_connection
from linkedout.intelligence.scoring.affinity_scorer import AffinityScorer
from organization.entities.app_user_entity import AppUserEntity
from shared.infra.db.cli_db import cli_db_manager
from shared.infra.db.db_session_manager import DbSessionType

MIN_FIRST_NAME_LEN = 3


def _load_company_names(session) -> set[str]:
    """Load all normalized company names for company-hint detection."""
    rows = session.execute(select(CompanyEntity.normalized_name)).all()
    return {row[0] for row in rows if row[0]}


def _load_experience_companies(session, crawled_profile_ids: list[str]) -> dict[str, set[str]]:
    """Load company names from experience records, keyed by crawled_profile_id."""
    if not crawled_profile_ids:
        return {}
    result: dict[str, set[str]] = defaultdict(set)
    stmt = (
        select(
            ExperienceEntity.crawled_profile_id,
            CompanyEntity.normalized_name,
        )
        .join(CompanyEntity, ExperienceEntity.company_id == CompanyEntity.id)
        .where(ExperienceEntity.crawled_profile_id.in_(crawled_profile_ids))
    )
    for cp_id, name in session.execute(stmt).all():
        if name:
            result[cp_id].add(name)
    return result


def _normalize_for_match(name: str) -> str:
    """Normalize a name for matching: lowercase, strip non-alpha."""
    return re.sub(r'[^a-z]', '', name.lower())


def _is_company_hint(last_name: str, company_names: set[str]) -> bool:
    """Check if a stub's last_name looks like a company name."""
    norm = _normalize_for_match(last_name)
    if not norm or len(norm) < 2:
        return False
    return norm in company_names


def _build_stub_snapshot(stub: ConnectionEntity, profile: CrawledProfileEntity) -> dict:
    """Capture stub data for the reconciliation log (enables rollback)."""
    return {
        'stub_connection_id': stub.id,
        'crawled_profile_id': stub.crawled_profile_id,
        'first_name': profile.first_name,
        'last_name': profile.last_name,
        'full_name': profile.full_name,
        'phones': stub.phones,
        'emails': stub.emails,
        'sources': stub.sources,
        'source_details': stub.source_details,
    }


def reconcile_for_user(session, app_user_id: str, dry_run: bool = False) -> list[dict]:
    """Run stub reconciliation for a single user. Returns list of merge log entries."""
    # Load LinkedIn connections (non-stub, active)
    linkedin_conns = session.execute(
        select(ConnectionEntity, CrawledProfileEntity)
        .join(CrawledProfileEntity, ConnectionEntity.crawled_profile_id == CrawledProfileEntity.id)
        .where(
            ConnectionEntity.app_user_id == app_user_id,
            ConnectionEntity.is_active.is_(True),
            ~CrawledProfileEntity.linkedin_url.like('stub://%'),
        )
    ).all()

    # Load stub connections (active, with phones, first_name >= MIN_FIRST_NAME_LEN chars)
    stubs = session.execute(
        select(ConnectionEntity, CrawledProfileEntity)
        .join(CrawledProfileEntity, ConnectionEntity.crawled_profile_id == CrawledProfileEntity.id)
        .where(
            ConnectionEntity.app_user_id == app_user_id,
            ConnectionEntity.is_active.is_(True),
            CrawledProfileEntity.linkedin_url.like('stub://%'),
            func.length(CrawledProfileEntity.first_name) >= MIN_FIRST_NAME_LEN,
        )
    ).all()

    if not stubs or not linkedin_conns:
        return []

    # Build first_name index for LinkedIn connections
    # key: normalized first_name -> list of (connection, profile)
    linkedin_by_fname: dict[str, list[tuple]] = defaultdict(list)
    for conn, profile in linkedin_conns:
        if profile.first_name and len(profile.first_name.strip()) >= MIN_FIRST_NAME_LEN:
            norm_fname = _normalize_for_match(profile.first_name)
            if norm_fname:
                linkedin_by_fname[norm_fname].append((conn, profile))

    # Load company names for Tier 2 company-hint detection
    company_names = _load_company_names(session)

    # Pre-fetch experience companies for LinkedIn connections (for Tier 2)
    li_profile_ids = [p.id for _, p in linkedin_conns]
    experience_companies = _load_experience_companies(session, li_profile_ids)

    # Name-swap preprocessing: build in-memory name overrides (don't mutate ORM entities)
    # key: stub connection id -> (effective_first_name, effective_last_name)
    name_overrides: dict[str, tuple[str, str | None]] = {}
    for stub_conn, stub_profile in stubs:
        fname = stub_profile.first_name
        lname = stub_profile.last_name
        if fname and _is_company_hint(fname, company_names):
            if lname and not _is_company_hint(lname, company_names):
                fname, lname = lname, fname
        name_overrides[stub_conn.id] = (fname, lname)

    merge_log: list[dict] = []

    for stub_conn, stub_profile in stubs:
        eff_fname, eff_lname = name_overrides.get(stub_conn.id, (stub_profile.first_name, stub_profile.last_name))
        if not eff_fname:
            continue
        norm_fname = _normalize_for_match(eff_fname)
        if not norm_fname:
            continue

        candidates = linkedin_by_fname.get(norm_fname, [])
        if not candidates:
            continue

        match = None
        tier = None
        confidence = 0.0

        if len(candidates) == 1:
            # Tier 1: unique first-name match
            target_conn, target_profile = candidates[0]
            confidence = 0.70
            # Boost confidence if last names match
            if (eff_lname and target_profile.last_name
                    and _normalize_for_match(eff_lname) == _normalize_for_match(target_profile.last_name)):
                confidence = 0.95
            match = target_conn
            tier = 'tier_1'

        elif 2 <= len(candidates) <= 5:
            # Tier 2: company-hint disambiguation
            stub_lname = eff_lname
            if not stub_lname:
                continue
            norm_lname = _normalize_for_match(stub_lname)
            if not norm_lname:
                continue

            if _is_company_hint(stub_lname, company_names):
                # Check which candidates have experience at this company
                matching_candidates = []
                for cand_conn, cand_profile in candidates:
                    cand_companies = experience_companies.get(cand_profile.id, set())
                    # Also check current_company_name
                    if cand_profile.current_company_name:
                        cand_companies.add(_normalize_for_match(cand_profile.current_company_name))
                    if norm_lname in cand_companies:
                        matching_candidates.append((cand_conn, cand_profile))

                if len(matching_candidates) == 1:
                    match = matching_candidates[0][0]
                    tier = 'tier_2'
                    confidence = 0.75
            else:
                # Treat as real last name: exact match against LinkedIn last names
                matching_candidates = []
                for cand_conn, cand_profile in candidates:
                    if (cand_profile.last_name
                            and _normalize_for_match(cand_profile.last_name) == norm_lname):
                        matching_candidates.append((cand_conn, cand_profile))

                if len(matching_candidates) == 1:
                    match = matching_candidates[0][0]
                    tier = 'tier_2'
                    confidence = 0.85

        if match is None:
            continue

        # Build log entry before merge (captures pre-merge state)
        log_entry = {
            'stub_connection_id': stub_conn.id,
            'target_connection_id': match.id,
            'tier': tier,
            'confidence': confidence,
            'stub_first_name': eff_fname,
            'stub_last_name': eff_lname,
            'stub_snapshot': _build_stub_snapshot(stub_conn, stub_profile),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        if not dry_run:
            merge_stub_into_connection(session, stub_conn, match)

        merge_log.append(log_entry)

    return merge_log


def _save_log(merge_log: list[dict], user_id: str) -> str:
    """Save reconciliation log to JSON file. Returns file path."""
    log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'reconciliation_logs')
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    path = os.path.join(log_dir, f'reconcile_{user_id}_{ts}.json')
    with open(path, 'w') as f:
        json.dump(merge_log, f, indent=2, default=str)
    return path


def main(user_id: str | None = None, dry_run: bool = False) -> int:
    db_manager = cli_db_manager()
    # First, resolve users without RLS (app_user table has no RLS)
    with db_manager.get_session(DbSessionType.READ) as session:
        if user_id:
            user = session.get(AppUserEntity, user_id)
            if not user:
                click.echo(f'User not found: {user_id}')
                return 1
            user_ids = [user.id]
        else:
            user_ids = [u.id for u in session.execute(
                select(AppUserEntity).where(AppUserEntity.is_active.is_(True))
            ).scalars().all()]

    click.echo(f'Reconciling stubs for {len(user_ids)} user(s)...')

    total_merges = 0
    all_logs: list[dict] = []

    # Process each user in a separate session with RLS context
    for uid in user_ids:
        with db_manager.get_session(DbSessionType.WRITE, app_user_id=uid) as session:
            merge_log = reconcile_for_user(session, uid, dry_run=dry_run)
            tier_1 = sum(1 for e in merge_log if e['tier'] == 'tier_1')
            tier_2 = sum(1 for e in merge_log if e['tier'] == 'tier_2')
            click.echo(f'  {uid}: {len(merge_log)} merges (tier 1: {tier_1}, tier 2: {tier_2})')

            if dry_run:
                for entry in merge_log:
                    click.echo(
                        f'    [DRY-RUN] {entry["tier"]} conf={entry["confidence"]:.2f} '
                        f'stub={entry["stub_connection_id"]} -> target={entry["target_connection_id"]} '
                        f'name={entry["stub_first_name"]} {entry.get("stub_last_name", "")}'
                    )

            all_logs.extend(merge_log)
            total_merges += len(merge_log)

            if merge_log and not dry_run:
                # Trigger affinity recompute within the same RLS session
                click.echo(f'  Recomputing affinity for {uid}...')
                scorer = AffinityScorer(session)
                count = scorer.compute_for_user(uid)
                click.echo(f'  {uid}: updated {count} connections')

    if all_logs and not dry_run:
        log_path = _save_log(all_logs, user_id or 'all')
        click.echo(f'Reconciliation log saved: {log_path}')

    click.echo(f'Done. Total merges: {total_merges}' + (' (dry run)' if dry_run else ''))

    return 0
