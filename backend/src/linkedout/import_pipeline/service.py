# SPDX-License-Identifier: Apache-2.0
"""ImportService — orchestrates parse → dedup → merge for CSV uploads."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, BinaryIO

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.contact_source.entities.contact_source_entity import ContactSourceEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.import_job.entities.import_job_entity import ImportJobEntity
from linkedout.import_pipeline.converters.registry import detect_converter, get_converter
from linkedout.import_pipeline.dedup import ConnectionLookupEntry, run_dedup
from linkedout.import_pipeline.merge import create_new_connection, merge_matched
from linkedout.import_pipeline.normalize import normalize_email
from shared.utils.linkedin_url import normalize_linkedin_url
from shared.utilities.logger import get_logger
from shared.utilities.metrics import record_metric

logger = get_logger(__name__, component="import")

# Google Contacts source types that should trigger post-import reconciliation
_GOOGLE_CONTACT_SOURCES = {'google_contacts_job', 'contacts_phone', 'google_contacts'}

IMPORT_SYNC_THRESHOLD = int(os.environ.get('IMPORT_SYNC_THRESHOLD', '5000'))


class ImportService:
    """Orchestrates the full import pipeline: parse → dedup → merge."""

    def __init__(self, session: Session):
        self._session = session

    def process_import(
        self,
        file: BinaryIO,
        file_name: str,
        tenant_id: str,
        bu_id: str,
        app_user_id: str,
        source_type: str | None = None,
    ) -> dict[str, Any]:
        """Run the full import pipeline synchronously.

        Returns import job summary dict.
        """
        import time as _time
        _start = _time.time()
        logger.info(f'Import starting: source={source_type or "auto"}, file={file_name}')

        # Step 1: Concurrent import guard (Decision #10)
        active_job = self._session.execute(
            select(ImportJobEntity).where(
                ImportJobEntity.app_user_id == app_user_id,
                ImportJobEntity.status.in_(['pending', 'processing']),
                ImportJobEntity.source_type == source_type if source_type else True,
            )
        ).scalar_one_or_none()

        if active_job:
            return {'error': 'conflict', 'message': 'An import is already in progress'}

        # Step 2: Create ImportJob
        import_job = ImportJobEntity(
            tenant_id=tenant_id,
            bu_id=bu_id,
            app_user_id=app_user_id,
            source_type=source_type or 'unknown',
            file_name=file_name,
            status='pending',
            started_at=datetime.now(timezone.utc),
        )
        self._session.add(import_job)
        self._session.flush()

        try:
            # Step 3: Get converter
            # 'google_contacts' is a generic frontend alias — use auto-detection
            # to pick the right sub-format (job, phone, email-only).
            use_auto_detect = not source_type or source_type == 'google_contacts'
            if not use_auto_detect:
                assert source_type  # guaranteed by use_auto_detect check above
                converter = get_converter(source_type)
            else:
                converter = detect_converter(file)
                if converter is None:
                    import_job.status = 'failed'
                    import_job.error_message = 'Could not detect file format'
                    self._session.flush()
                    return self._job_summary(import_job)
                source_type = converter.source_type
                import_job.source_type = source_type

            # Step 4: Parse
            parsed_contacts, failed_rows = converter.parse(file)
            import_job.total_records = len(parsed_contacts) + len(failed_rows)
            import_job.failed_count = len(failed_rows)
            import_job.parsed_count = len(parsed_contacts)
            import_job.status = 'parsing'
            self._session.flush()

            if not parsed_contacts:
                import_job.status = 'complete'
                import_job.completed_at = datetime.now(timezone.utc)
                self._session.flush()
                return self._job_summary(import_job, failed_rows)

            # Step 5: Check sync/async threshold
            if len(parsed_contacts) > IMPORT_SYNC_THRESHOLD:
                import_job.status = 'processing'
                self._session.flush()
                return self._job_summary(import_job, failed_rows, async_mode=True)

            # Step 6: Bulk insert ContactSource rows
            cs_dicts = []
            for pc in parsed_contacts:
                norm_url = normalize_linkedin_url(pc.linkedin_url) if pc.linkedin_url else None
                cs_dicts.append({
                    'tenant_id': tenant_id,
                    'bu_id': bu_id,
                    'app_user_id': app_user_id,
                    'import_job_id': import_job.id,
                    'source_type': source_type,
                    'source_file_name': file_name,
                    'first_name': pc.first_name,
                    'last_name': pc.last_name,
                    'full_name': pc.full_name,
                    'email': normalize_email(pc.email) if pc.email else None,
                    'phone': pc.phone,
                    'company': pc.company,
                    'title': pc.title,
                    'linkedin_url': norm_url,
                    'connected_at': pc.connected_at,
                    'raw_record': pc.raw_record,
                    'dedup_status': 'pending',
                })

            self._session.execute(insert(ContactSourceEntity), cs_dicts)
            self._session.flush()

            # Reload contact sources for dedup
            contact_sources = list(
                self._session.execute(
                    select(ContactSourceEntity).where(
                        ContactSourceEntity.import_job_id == import_job.id
                    )
                ).scalars().all()
            )

            import_job.status = 'deduplicating'
            self._session.flush()

            # Step 7: Build lookup entries from existing connections
            lookup_entries = self._build_connection_lookups(app_user_id)

            # Step 8: Run dedup
            run_dedup(contact_sources, lookup_entries)
            self._session.flush()

            # Step 9: Merge
            matched_count, new_count = self._run_merge(
                contact_sources, tenant_id, bu_id, app_user_id
            )

            # Step 10: Update import job
            import_job.matched_count = matched_count
            import_job.new_count = new_count
            import_job.status = 'complete'
            import_job.completed_at = datetime.now(timezone.utc)
            self._session.flush()

            # Step 11: Post-import reconciliation for Google Contacts imports
            if source_type in _GOOGLE_CONTACT_SOURCES and new_count > 0:
                self._run_post_import_reconciliation(app_user_id)

            _duration_ms = (_time.time() - _start) * 1000
            logger.info(
                f'Import complete: source={source_type}, '
                f'parsed={import_job.parsed_count}, matched={matched_count}, '
                f'new={new_count}, failed={import_job.failed_count}, '
                f'{_duration_ms:.0f}ms'
            )
            record_metric(
                "profiles_imported", import_job.parsed_count or 0,
                source=source_type or "unknown", duration_ms=_duration_ms,
                matched=matched_count, new=new_count,
                failed=import_job.failed_count or 0,
            )

            return self._job_summary(import_job, failed_rows)

        except Exception as e:
            logger.error(f'Import failed: {e}')
            import_job.status = 'failed'
            import_job.error_message = str(e)[:500]
            import_job.completed_at = datetime.now(timezone.utc)
            self._session.flush()
            raise

    def get_import_job(self, job_id: str) -> ImportJobEntity | None:
        """Get an import job by ID."""
        return self._session.execute(
            select(ImportJobEntity).where(ImportJobEntity.id == job_id)
        ).scalar_one_or_none()

    def _build_connection_lookups(self, app_user_id: str) -> list[ConnectionLookupEntry]:
        """Load all connections for user and build lookup entries."""
        # Join connections with crawled_profiles to get linkedin_url and name
        rows = self._session.execute(
            select(
                ConnectionEntity.id,
                ConnectionEntity.emails,
                CrawledProfileEntity.linkedin_url,
                CrawledProfileEntity.previous_linkedin_url,
                CrawledProfileEntity.full_name,
                CrawledProfileEntity.current_company_name,
            ).join(
                CrawledProfileEntity,
                ConnectionEntity.crawled_profile_id == CrawledProfileEntity.id,
            ).where(
                ConnectionEntity.app_user_id == app_user_id,
            )
        ).all()

        entries = []
        for row in rows:
            conn_id, emails_csv, li_url, prev_li_url, full_name, company = row
            norm_url = normalize_linkedin_url(li_url) if li_url else None
            norm_prev_url = normalize_linkedin_url(prev_li_url) if prev_li_url else None
            norm_emails = []
            if emails_csv:
                for em in emails_csv.split(','):
                    ne = normalize_email(em)
                    if ne:
                        norm_emails.append(ne)

            entries.append(ConnectionLookupEntry(
                connection_id=conn_id,
                linkedin_url=norm_url,
                emails=norm_emails or None,
                full_name=full_name,
                company=company,
            ))
            # Add duplicate entry with previous URL for redirect dedup
            if norm_prev_url and norm_prev_url != norm_url:
                entries.append(ConnectionLookupEntry(
                    connection_id=conn_id,
                    linkedin_url=norm_prev_url,
                    emails=norm_emails or None,
                    full_name=full_name,
                    company=company,
                ))

        return entries

    def _run_post_import_reconciliation(self, app_user_id: str) -> None:
        """Run stub reconciliation after a Google Contacts import creates new stubs."""
        try:
            from dev_tools.reconcile_stubs import reconcile_for_user
            merge_log = reconcile_for_user(self._session, app_user_id)
            if merge_log:
                logger.info(f'Post-import reconciliation: merged {len(merge_log)} stubs for {app_user_id}')
        except Exception as e:
            # Reconciliation failure should not fail the import
            logger.warning(f'Post-import reconciliation failed for {app_user_id}: {e}')

    def _run_merge(
        self,
        contact_sources: list[ContactSourceEntity],
        tenant_id: str,
        bu_id: str,
        app_user_id: str,
    ) -> tuple[int, int]:
        """Merge matched/new contacts. Returns (matched_count, new_count)."""
        matched_count = 0
        new_count = 0

        # Pre-load existing crawled profiles by URL for new contact creation
        existing_profiles: dict[str, CrawledProfileEntity] = {}
        profile_rows = self._session.execute(select(CrawledProfileEntity)).scalars().all()
        for p in profile_rows:
            norm = normalize_linkedin_url(p.linkedin_url) if p.linkedin_url else None
            if norm:
                existing_profiles[norm] = p
            # Also index by previous URL for redirect dedup safety
            prev = normalize_linkedin_url(p.previous_linkedin_url) if p.previous_linkedin_url else None
            if prev and prev not in existing_profiles:
                existing_profiles[prev] = p

        # Pre-load connections by ID for merge_matched
        connections_by_id: dict[str, ConnectionEntity] = {}

        for cs in contact_sources:
            if cs.dedup_status == 'matched' and cs.connection_id:
                if cs.connection_id not in connections_by_id:
                    conn = self._session.execute(
                        select(ConnectionEntity).where(ConnectionEntity.id == cs.connection_id)
                    ).scalar_one_or_none()
                    if conn:
                        connections_by_id[cs.connection_id] = conn

                conn = connections_by_id.get(cs.connection_id)
                if conn:
                    merge_matched(conn, cs)
                    matched_count += 1

            elif cs.dedup_status == 'new':
                create_new_connection(
                    self._session, cs, existing_profiles,
                    tenant_id, bu_id, app_user_id,
                )
                new_count += 1

        self._session.flush()
        return matched_count, new_count

    def _job_summary(
        self,
        job: ImportJobEntity,
        failed_rows: list | None = None,
        async_mode: bool = False,
    ) -> dict[str, Any]:
        summary = {
            'import_job_id': job.id,
            'status': job.status,
            'total_records': job.total_records,
            'parsed_count': job.parsed_count,
            'matched_count': job.matched_count,
            'new_count': job.new_count,
            'failed_count': job.failed_count,
        }
        if failed_rows:
            summary['failed_rows'] = [
                {'row': r[0], 'error': r[2]} for r in failed_rows
            ]
        if async_mode:
            summary['async'] = True
        return summary
