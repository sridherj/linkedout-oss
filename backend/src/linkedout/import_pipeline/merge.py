# SPDX-License-Identifier: Apache-2.0
"""Golden record merge: update matched connections or create new ones.

Survivorship rules:
- connected_at: earliest date wins
- company/title: LinkedIn CSV wins over Google/phone sources
- Email/phone: any non-null source fills in missing
- sources: append, don't duplicate
"""
from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

from shared.utils.linkedin_url import normalize_linkedin_url

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from linkedout.connection.entities.connection_entity import ConnectionEntity
    from linkedout.contact_source.entities.contact_source_entity import ContactSourceEntity
    from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity


# Sources where company/title data is authoritative
_LINKEDIN_SOURCES = {'linkedin_csv'}


def merge_matched(
    connection: ConnectionEntity,
    contact_source: ContactSourceEntity,
) -> None:
    """Merge data from a matched contact_source into an existing connection.

    Mutates connection in-place.
    """
    source_type = contact_source.source_type

    # Append source if not already present
    if connection.sources is None:
        connection.sources = []
    if source_type not in connection.sources:
        connection.sources = connection.sources + [source_type]

    # Merge emails: union
    if contact_source.email:
        existing = set(_split_csv(connection.emails))
        existing.add(contact_source.email.strip().lower())
        connection.emails = ','.join(sorted(existing))

    # Merge phones: union
    if contact_source.phone:
        existing = set(_split_csv(connection.phones))
        existing.add(contact_source.phone.strip())
        connection.phones = ','.join(sorted(existing))

    # connected_at: earliest wins
    if contact_source.connected_at:
        cs_date = contact_source.connected_at
        if isinstance(cs_date, str):
            try:
                cs_date = date.fromisoformat(cs_date)
            except (ValueError, TypeError):
                cs_date = None
        if cs_date and (connection.connected_at is None or cs_date < connection.connected_at):
            connection.connected_at = cs_date

    # Append source detail
    _append_source_detail(connection, contact_source)

    # Link contact_source to connection
    contact_source.connection_id = connection.id


def create_new_connection(
    session: Session,
    contact_source: ContactSourceEntity,
    existing_profiles_by_url: dict[str, CrawledProfileEntity],
    tenant_id: str,
    bu_id: str,
    app_user_id: str,
) -> ConnectionEntity:
    """Create a new connection (+ stub crawled_profile if needed).

    connection.crawled_profile_id is never NULL.
    """
    from linkedout.connection.entities.connection_entity import ConnectionEntity as ConnEntity
    from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity as CPEntity

    norm_url = normalize_linkedin_url(contact_source.linkedin_url) if contact_source.linkedin_url else None

    # Find or create crawled_profile
    profile = existing_profiles_by_url.get(norm_url) if norm_url else None

    if profile is None:
        # Create stub crawled_profile
        profile = CPEntity(
            linkedin_url=norm_url or f'stub://{contact_source.id}',
            first_name=contact_source.first_name,
            last_name=contact_source.last_name,
            full_name=contact_source.full_name or _build_name(
                contact_source.first_name, contact_source.last_name
            ),
            current_company_name=contact_source.company,
            current_position=contact_source.title,
            data_source='csv_stub',
            has_enriched_data=False,
        )
        session.add(profile)
        session.flush()  # get the ID
        if norm_url:
            existing_profiles_by_url[norm_url] = profile

    connection = ConnEntity(
        tenant_id=tenant_id,
        bu_id=bu_id,
        app_user_id=app_user_id,
        crawled_profile_id=profile.id,
        sources=[contact_source.source_type],
        emails=contact_source.email or None,
        phones=contact_source.phone or None,
        connected_at=contact_source.connected_at,
    )
    session.add(connection)
    session.flush()

    # Link contact_source
    contact_source.connection_id = connection.id

    return connection


def merge_stub_into_connection(
    session: Session,
    stub: ConnectionEntity,
    target: ConnectionEntity,
) -> None:
    """Merge a stub connection into an existing LinkedIn connection.

    Moves phones, emails, source_details, and sources from stub to target.
    Repoints all contact_source records from stub to target.
    Soft-deletes the stub connection and its crawled_profile.
    Mutates target and stub in-place.
    """
    from linkedout.contact_source.entities.contact_source_entity import ContactSourceEntity as CSEntity
    from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity as CPEntity

    # Merge phones
    if stub.phones:
        existing = set(_split_csv(target.phones))
        for phone in _split_csv(stub.phones):
            existing.add(phone)
        target.phones = ','.join(sorted(existing)) if existing else None

    # Merge emails
    if stub.emails:
        existing = set(_split_csv(target.emails))
        for email in _split_csv(stub.emails):
            existing.add(email.lower())
        target.emails = ','.join(sorted(existing)) if existing else None

    # Merge sources array
    if stub.sources:
        target_sources = list(target.sources or [])
        for src in stub.sources:
            if src not in target_sources:
                target_sources.append(src)
        target.sources = target_sources

    # Merge source_details
    _merge_source_details(target, stub)

    # connected_at: earliest wins
    if stub.connected_at and (target.connected_at is None or stub.connected_at < target.connected_at):
        target.connected_at = stub.connected_at

    # Repoint contact_source records from stub to target
    from sqlalchemy import update
    session.execute(
        update(CSEntity)
        .where(CSEntity.connection_id == stub.id)
        .values(connection_id=target.id)
    )

    # Soft-delete stub connection
    stub.is_active = False

    # Soft-delete stub's crawled_profile if it's a stub profile
    if stub.crawled_profile_id:
        stub_profile = session.get(CPEntity, stub.crawled_profile_id)
        if stub_profile and (stub_profile.linkedin_url or '').startswith('stub://'):
            stub_profile.is_active = False

    session.flush()


def _merge_source_details(target: ConnectionEntity, stub: ConnectionEntity) -> None:
    """Merge source_details JSON from stub into target."""
    try:
        target_details = json.loads(target.source_details) if target.source_details else []
    except (json.JSONDecodeError, TypeError):
        target_details = []
    if not isinstance(target_details, list):
        target_details = []

    try:
        stub_details = json.loads(stub.source_details) if stub.source_details else []
    except (json.JSONDecodeError, TypeError):
        stub_details = []
    if not isinstance(stub_details, list):
        stub_details = []

    target_details.extend(stub_details)
    target.source_details = json.dumps(target_details) if target_details else None


def _split_csv(value: str | None) -> list[str]:
    """Split comma-separated string, stripping whitespace, filtering empty."""
    if not value:
        return []
    return [v.strip() for v in value.split(',') if v.strip()]


def _build_name(first: str | None, last: str | None) -> str | None:
    parts = [p for p in (first, last) if p and p.strip()]
    return ' '.join(parts) if parts else None


def _append_source_detail(connection: ConnectionEntity, cs: ContactSourceEntity) -> None:
    """Append a source entry to connection.source_details JSON."""
    try:
        details = json.loads(connection.source_details) if connection.source_details else []
    except (json.JSONDecodeError, TypeError):
        details = []
    if not isinstance(details, list):
        details = []

    details.append({
        'source_type': cs.source_type,
        'contact_source_id': cs.id if hasattr(cs, 'id') else None,
        'email': cs.email,
        'phone': cs.phone,
        'company': cs.company,
        'title': cs.title,
    })
    connection.source_details = json.dumps(details)
