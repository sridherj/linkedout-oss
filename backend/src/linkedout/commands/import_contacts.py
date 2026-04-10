# SPDX-License-Identifier: Apache-2.0
"""``linkedout import-contacts`` — import Google/iCloud contacts from CSV/vCard.

Parses contacts from multiple source formats, matches them to existing
connections (by email or name+company), and merges additional data.
Unmatched contacts create new stub connections.
"""
import csv
import json
import re
import time
from dataclasses import dataclass
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path

import click
from sqlalchemy import text
from sqlalchemy.orm import Session

from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.contact_source.entities.contact_source_entity import ContactSourceEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.import_job.entities.import_job_entity import ImportJobEntity
from linkedout.cli_helpers import cli_logged
from dev_tools.db.fixed_data import SYSTEM_USER_ID
from shared.infra.db.cli_db import cli_db_manager
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger
from shared.utilities.metrics import record_metric
from shared.utilities.operation_report import OperationCounts, OperationReport

# SJ's system user IDs
APP_USER_ID = 'usr_sys_001'
TENANT_ID = 'tenant_sys_001'
BU_ID = 'bu_sys_001'

# Source priority (higher = more authoritative)
SOURCE_PRIORITY = {
    'linkedin_csv': 4,
    'google_job_contacts': 3,
    'phone_contacts': 2,
    'email_only_contacts': 1,
}

# Map internal source names to EXTERNAL_SOURCE_TYPES used by affinity scorer
SOURCE_TYPE_MAP = {
    'google_job_contacts': 'google_contacts_job',
    'phone_contacts': 'contacts_phone',
    'email_only_contacts': 'gmail_email_only',
}

# Map internal source names to source_label on contact_source
SOURCE_LABEL_MAP = {
    'google_job_contacts': 'google_work',
    'phone_contacts': 'google_personal',
    'email_only_contacts': 'google_personal',
}


@dataclass
class ParsedContact:
    """Normalized contact from any source."""
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    title: str | None = None
    source: str = ''


# --- Per-Source Converters ---


def parse_google_job_contacts(csv_path: Path) -> list[ParsedContact]:
    """Parse contacts_from_google_job.csv (Google Contacts 31-col format)."""
    contacts = []
    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = (row.get('E-mail 1 - Value') or '').strip()
            if not email:
                continue

            contacts.append(ParsedContact(
                first_name=(row.get('Given Name') or '').strip() or None,
                last_name=(row.get('Family Name') or '').strip() or None,
                full_name=(row.get('Name') or '').strip() or None,
                email=email.lower(),
                source='google_job_contacts',
            ))
    return contacts


def normalize_phone(raw_phone: str, default_country: str = 'IN') -> str | None:
    """Basic phone normalization -- strip non-digits, add country code if needed."""
    if not raw_phone or not raw_phone.strip():
        return None

    cleaned = raw_phone.strip()
    has_plus = cleaned.startswith('+')
    digits = re.sub(r'[^\d]', '', cleaned)

    if not digits or len(digits) < 7:
        return None

    if has_plus:
        return f'+{digits}'

    # Indian numbers (10 digits, starts with 6-9)
    if default_country == 'IN' and len(digits) == 10 and digits[0] in '6789':
        return f'+91{digits}'

    # US numbers (10 digits)
    if len(digits) == 10:
        return f'+1{digits}'

    # 11+ digits -- assume country code included
    if len(digits) >= 11:
        return f'+{digits}'

    return digits


def parse_phone_contacts(csv_path: Path) -> list[ParsedContact]:
    """Parse contacts_with_phone.csv (Outlook-style 67-col format)."""
    contacts = []
    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            first_name = (row.get('First Name') or '').strip() or None
            last_name = (row.get('Last Name') or '').strip() or None

            phone = None
            for col in ['Mobile Phone', 'Primary Phone', 'Home Phone']:
                raw = (row.get(col) or '').strip()
                if raw:
                    phone = normalize_phone(raw)
                    if phone:
                        break

            email = (row.get('E-mail Address') or '').strip() or None
            company = (row.get('Company') or '').strip() or None
            title = (row.get('Job Title') or '').strip() or None

            if not phone and not email:
                continue

            full_name = f'{first_name or ""} {last_name or ""}'.strip() or None

            contacts.append(ParsedContact(
                first_name=first_name,
                last_name=last_name,
                full_name=full_name,
                email=email.lower() if email else None,
                phone=phone,
                company=company,
                title=title,
                source='phone_contacts',
            ))
    return contacts


def _is_valid_name(name: str | None) -> bool:
    """Reject names that are email-like or purely numeric."""
    if not name:
        return False
    if '@' in name:
        return False
    if name.replace(' ', '').isdigit():
        return False
    return True


def parse_email_only_contacts(csv_path: Path) -> list[ParsedContact]:
    """Parse gmail_contacts_email_id_only.csv (Google Contacts 27-col format)."""
    contacts = []
    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = (row.get('E-mail 1 - Value') or '').strip()
            if not email:
                continue

            first_name = (row.get('First Name') or '').strip() or None
            last_name = (row.get('Last Name') or '').strip() or None

            if not _is_valid_name(first_name):
                first_name = None
            if not _is_valid_name(last_name):
                last_name = None

            full_name = f'{first_name or ""} {last_name or ""}'.strip() or None

            contacts.append(ParsedContact(
                first_name=first_name,
                last_name=last_name,
                full_name=full_name,
                email=email.lower(),
                source='email_only_contacts',
            ))
    return contacts


# --- Cross-Source Dedup ---


def dedup_contacts(all_contacts: list[ParsedContact]) -> list[ParsedContact]:
    """Deduplicate contacts across sources by email. Higher-priority source wins."""
    seen_emails: dict[str, ParsedContact] = {}
    no_email: list[ParsedContact] = []

    sorted_contacts = sorted(
        all_contacts,
        key=lambda c: SOURCE_PRIORITY.get(c.source, 0),
        reverse=True,
    )

    for contact in sorted_contacts:
        if contact.email:
            if contact.email not in seen_emails:
                seen_emails[contact.email] = contact
            else:
                existing = seen_emails[contact.email]
                if not existing.phone and contact.phone:
                    existing.phone = contact.phone
        else:
            no_email.append(contact)

    return list(seen_emails.values()) + no_email


# --- Matching & Merging ---


def build_email_index(session: Session) -> dict[str, tuple[str, str]]:
    """Build {email: (connection_id, current_sources)} lookup from existing connections."""
    rows = session.execute(
        text("SELECT id, emails, sources FROM connection WHERE emails IS NOT NULL AND emails != ''")
    ).fetchall()
    index: dict[str, tuple[str, str]] = {}
    for conn_id, emails_str, sources in rows:
        if emails_str:
            for email in emails_str.split(','):
                email = email.strip().lower()
                if email:
                    index[email] = (conn_id, sources)
    return index


def build_name_index(session: Session) -> dict[str, str]:
    """Build {lower(full_name): connection_id} from crawled_profile + connection."""
    rows = session.execute(text("""
        SELECT c.id, cp.full_name
        FROM connection c
        JOIN crawled_profile cp ON c.crawled_profile_id = cp.id
        WHERE cp.full_name IS NOT NULL
    """)).fetchall()
    return {name.strip().lower(): conn_id for conn_id, name in rows if name}


def merge_contact_onto_connection(
    session: Session,
    conn_id: str,
    contact: ParsedContact,
) -> None:
    """Merge email/phone from contact onto existing connection."""
    updates = []
    params: dict = {'conn_id': conn_id}

    if contact.email:
        row = session.execute(
            text('SELECT emails, sources FROM connection WHERE id = :id'),
            {'id': conn_id},
        ).fetchone()
        if row:
            existing_emails = (row[0] or '').lower()
            if contact.email not in existing_emails:
                new_emails = f'{row[0]},{contact.email}' if row[0] else contact.email
                updates.append('emails = :emails')
                params['emails'] = new_emails

            existing_sources = row[1] or []
            source_tag = 'google_contacts'
            if source_tag not in existing_sources:
                updates.append(f"sources = array_append(sources, '{source_tag}')")

    if contact.phone:
        row2 = session.execute(
            text('SELECT phones FROM connection WHERE id = :id'),
            {'id': conn_id},
        ).fetchone()
        if row2:
            existing_phones = (row2[0] or '').lower()
            if contact.phone not in existing_phones:
                new_phones = f'{row2[0]},{contact.phone}' if row2[0] else contact.phone
                updates.append('phones = :phones')
                params['phones'] = new_phones

    if updates:
        sql = f"UPDATE connection SET {', '.join(updates)} WHERE id = :conn_id"
        session.execute(text(sql), params)


def create_contact_connection(
    session: Session,
    contact: ParsedContact,
    now: datetime,
) -> None:
    """Create a new stub profile + connection for unmatched contacts."""
    stub = CrawledProfileEntity(
        linkedin_url=f'stub://gmail-{contact.email or contact.phone or uuid4().hex}',
        first_name=contact.first_name,
        last_name=contact.last_name,
        full_name=contact.full_name,
        current_company_name=contact.company,
        current_position=contact.title,
        data_source='gmail_stub',
        has_enriched_data=False,
        last_crawled_at=now,
    )
    session.add(stub)
    session.flush()

    source_details = json.dumps({
        'first_name': contact.first_name,
        'last_name': contact.last_name,
        'email': contact.email,
        'phone': contact.phone,
        'company': contact.company,
        'title': contact.title,
        'gmail_source': contact.source,
    })

    connection = ConnectionEntity(
        app_user_id=APP_USER_ID,
        crawled_profile_id=stub.id,
        tenant_id=TENANT_ID,
        bu_id=BU_ID,
        emails=contact.email,
        phones=contact.phone,
        sources=['google_contacts'],
        source_details=source_details,
    )
    session.add(connection)


def _create_contact_source(
    session: Session,
    contact: ParsedContact,
    import_job_id: str,
    connection_id: str | None,
    dedup_status: str,
    dedup_method: str | None,
) -> None:
    """Write a contact_source row for the affinity scorer's external contact signal."""
    cs = ContactSourceEntity(
        app_user_id=APP_USER_ID,
        tenant_id=TENANT_ID,
        bu_id=BU_ID,
        import_job_id=import_job_id,
        source_type=SOURCE_TYPE_MAP.get(contact.source, contact.source),
        source_label=SOURCE_LABEL_MAP.get(contact.source),
        source_file_name=contact.source,
        first_name=contact.first_name,
        last_name=contact.last_name,
        full_name=contact.full_name,
        email=contact.email,
        phone=contact.phone,
        company=contact.company,
        title=contact.title,
        connection_id=connection_id,
        dedup_status=dedup_status,
        dedup_method=dedup_method,
    )
    session.add(cs)


def process_contacts(
    session: Session,
    contacts: list[ParsedContact],
    email_index: dict[str, tuple[str, str]],
    name_index: dict[str, str],
    now: datetime,
    import_job_id: str = '',
) -> dict[str, int]:
    """Match and merge contacts. Returns counts per outcome."""
    stats = {'matched_email': 0, 'matched_name': 0, 'new': 0, 'errors': 0}

    for contact in contacts:
        savepoint = session.begin_nested()
        try:
            if contact.email and contact.email in email_index:
                conn_id, _ = email_index[contact.email]
                merge_contact_onto_connection(session, conn_id, contact)
                _create_contact_source(session, contact, import_job_id, conn_id, 'matched', 'email')
                stats['matched_email'] += 1
                savepoint.commit()
                continue

            if contact.full_name:
                name_key = contact.full_name.strip().lower()
                if name_key in name_index:
                    conn_id = name_index[name_key]
                    merge_contact_onto_connection(session, conn_id, contact)
                    _create_contact_source(
                        session, contact, import_job_id, conn_id, 'matched', 'name',
                    )
                    stats['matched_name'] += 1
                    savepoint.commit()
                    continue

            create_contact_connection(session, contact, now)
            session.flush()
            stub_url = f'stub://gmail-{contact.email or contact.phone or ""}'
            row = session.execute(
                text("""
                    SELECT c.id FROM connection c
                    JOIN crawled_profile cp ON c.crawled_profile_id = cp.id
                    WHERE cp.linkedin_url = :url AND c.app_user_id = :uid
                    ORDER BY c.created_at DESC LIMIT 1
                """),
                {'url': stub_url, 'uid': APP_USER_ID},
            ).fetchone()
            new_conn_id = row[0] if row else None
            _create_contact_source(session, contact, import_job_id, new_conn_id, 'new', None)
            stats['new'] += 1
            savepoint.commit()

        except Exception as e:
            savepoint.rollback()
            stats['errors'] += 1
            click.echo(f'  Error on contact ({contact.full_name}, {contact.email}): {e}', err=True)

    return stats


logger = get_logger(__name__, component="import", operation="import_contacts")


@click.command('import-contacts')
@click.argument('contacts_dir', default='', required=False)
@click.option('--format', 'fmt', type=click.Choice(['google', 'icloud', 'auto']),
              default='auto', help='Contact format: google, icloud, auto (default: auto)')
@click.option('--dry-run', is_flag=True, help='Parse and report only, do not write to DB')
@cli_logged("import_contacts")
def import_contacts_command(contacts_dir: str, fmt: str, dry_run: bool):
    """Import Google contacts from CSV/vCard."""
    db_manager = cli_db_manager()
    start_time = time.time()

    if contacts_dir:
        gmail_path = Path(contacts_dir)
    else:
        gmail_path = Path.home() / 'Downloads'

    # Parse all 3 sources (each file is optional)
    google_job_path = gmail_path / 'contacts_from_google_job.csv'
    phone_path = gmail_path / 'contacts_with_phone.csv'
    email_only_path = gmail_path / 'gmail_contacts_email_id_only.csv'

    found_any = any(p.exists() for p in [google_job_path, phone_path, email_only_path])
    if not found_any:
        click.echo(f'No contact files found in {gmail_path}. Nothing to import.')
        return

    click.echo('Parsing contact sources...')
    google_job: list[ParsedContact] = []
    if google_job_path.exists():
        google_job = parse_google_job_contacts(google_job_path)
        click.echo(f'  Google Job:   {len(google_job):>6} contacts')
    else:
        click.echo(f'  Google Job:   (skipped — {google_job_path.name} not found)')

    phone: list[ParsedContact] = []
    if phone_path.exists():
        phone = parse_phone_contacts(phone_path)
        click.echo(f'  Phone:        {len(phone):>6} contacts')
    else:
        click.echo(f'  Phone:        (skipped — {phone_path.name} not found)')

    email_only: list[ParsedContact] = []
    if email_only_path.exists():
        email_only = parse_email_only_contacts(email_only_path)
        click.echo(f'  Email-Only:   {len(email_only):>6} contacts')
    else:
        click.echo(f'  Email-Only:   (skipped — {email_only_path.name} not found)')

    all_contacts = google_job + phone + email_only
    deduped = dedup_contacts(all_contacts)
    click.echo(f'\n  Total parsed: {len(all_contacts):>6}')
    click.echo(f'  After dedup:  {len(deduped):>6}')

    if dry_run:
        click.echo('\n--- DRY RUN COMPLETE ---')
        return

    click.echo('\nBuilding match indexes...')
    with db_manager.get_session(DbSessionType.READ, app_user_id=SYSTEM_USER_ID) as session:
        email_index = build_email_index(session)
        name_index = build_name_index(session)
    click.echo(f'  Email index:  {len(email_index):>6} entries')
    click.echo(f'  Name index:   {len(name_index):>6} entries')

    click.echo('\nMatching and merging contacts...')
    now = datetime.now(timezone.utc)

    with db_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
        prior_count = session.execute(text(
            "DELETE FROM contact_source WHERE source_type IN "
            "('google_contacts_job', 'contacts_phone', 'gmail_email_only')"
        )).rowcount
        if prior_count:
            click.echo(f'  Cleaned up {prior_count} prior contact_source rows')

        import_job = ImportJobEntity(
            app_user_id=APP_USER_ID,
            tenant_id=TENANT_ID,
            bu_id=BU_ID,
            source_type='gmail_contacts',
            file_name='gmail_contacts_dir',
            status='processing',
            total_records=len(deduped),
            started_at=now,
        )
        session.add(import_job)
        session.flush()

        stats = process_contacts(session, deduped, email_index, name_index, now, import_job.id)

        import_job.status = 'complete'
        import_job.parsed_count = len(deduped)
        import_job.matched_count = stats['matched_email'] + stats['matched_name']
        import_job.new_count = stats['new']
        import_job.failed_count = stats['errors']
        import_job.completed_at = datetime.now(timezone.utc)
        session.flush()

    elapsed = time.time() - start_time
    duration_ms = elapsed * 1000
    matched = stats['matched_email'] + stats['matched_name']

    logger.info(
        f'Contact import complete: {len(deduped)} contacts, '
        f'{matched} matched, {stats["new"]} new, {stats["errors"]} errors, '
        f'{duration_ms:.0f}ms'
    )
    record_metric(
        'contacts_imported', len(deduped),
        source='gmail', duration_ms=duration_ms,
        matched=matched, new=stats['new'], errors=stats['errors'],
    )

    report = OperationReport(
        operation='import-contacts',
        duration_ms=duration_ms,
        counts=OperationCounts(
            total=len(deduped),
            succeeded=matched + stats['new'],
            skipped=0,
            failed=stats['errors'],
        ),
        next_steps=[
            'Run `linkedout compute-affinity` to recalculate affinity scores',
        ],
    )
    report_path = report.save()

    click.echo('\nResults:')
    click.echo(f'  Matched (email): {stats["matched_email"]:>6}')
    click.echo(f'  Matched (name):  {stats["matched_name"]:>6}')
    click.echo(f'  New connections:  {stats["new"]:>6}')
    click.echo(f'  Errors:          {stats["errors"]:>6}')
    click.echo(f'  Elapsed:         {elapsed:>5.1f}s')

    click.echo('\nNext steps:')
    click.echo('  -> Run `linkedout compute-affinity` to recalculate affinity scores')

    try:
        display = '~/' + str(report_path.relative_to(Path.home()))
    except ValueError:
        display = str(report_path)
    click.echo(f'\nReport saved: {display}')
