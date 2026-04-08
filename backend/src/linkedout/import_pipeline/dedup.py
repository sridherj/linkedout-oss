# SPDX-License-Identifier: Apache-2.0
"""Cascading dedup pipeline: URL → Email → Fuzzy Name+Company → New.

Single in-memory load of all connections, three pure-Python stages.
All stages are pure Python against in-memory dicts — one DB round-trip to load.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rapidfuzz.fuzz import token_sort_ratio

from linkedout.import_pipeline.normalize import normalize_email
from shared.utils.linkedin_url import normalize_linkedin_url

if TYPE_CHECKING:
    from linkedout.contact_source.entities.contact_source_entity import ContactSourceEntity


@dataclass
class ConnectionLookupEntry:
    """Pre-built lookup entry for a connection."""
    connection_id: str
    linkedin_url: str | None = None  # normalized
    emails: list[str] | None = None  # normalized
    full_name: str | None = None
    company: str | None = None


def build_lookup_dicts(
    entries: list[ConnectionLookupEntry],
) -> tuple[dict[str, str], dict[str, str], list[ConnectionLookupEntry]]:
    """Build URL and email lookup dicts from connection entries.

    Returns:
        (url_to_conn_id, email_to_conn_id, name_entries_for_fuzzy)
    """
    url_map: dict[str, str] = {}
    email_map: dict[str, str] = {}
    name_entries: list[ConnectionLookupEntry] = []

    for entry in entries:
        if entry.linkedin_url:
            url_map[entry.linkedin_url] = entry.connection_id
        if entry.emails:
            for em in entry.emails:
                if em:
                    email_map[em] = entry.connection_id
        if entry.full_name:
            name_entries.append(entry)

    return url_map, email_map, name_entries


def run_dedup(
    contact_sources: list[ContactSourceEntity],
    lookup_entries: list[ConnectionLookupEntry],
) -> None:
    """Run 3-stage cascading dedup. Mutates contact_sources in-place.

    Sets dedup_status, dedup_method, dedup_confidence, and connection_id.
    """
    url_map, email_map, name_entries = build_lookup_dicts(lookup_entries)

    # Track within-import URL dedup
    import_url_seen: dict[str, int] = {}

    unmatched_indices: list[int] = list(range(len(contact_sources)))

    # Stage 1: Exact LinkedIn URL match (confidence 1.0)
    still_unmatched: list[int] = []
    for idx in unmatched_indices:
        cs = contact_sources[idx]
        norm_url = normalize_linkedin_url(cs.linkedin_url) if cs.linkedin_url else None
        if norm_url:
            conn_id = url_map.get(norm_url)
            if conn_id:
                _mark_matched(cs, conn_id, 'exact_url', 1.0)
                import_url_seen[norm_url] = idx
                continue
            # Within-import dedup: if same URL seen earlier and that was matched
            if norm_url in import_url_seen:
                first = contact_sources[import_url_seen[norm_url]]
                if first.connection_id:
                    _mark_matched(cs, first.connection_id, 'exact_url', 1.0)
                    continue
            import_url_seen[norm_url] = idx
        still_unmatched.append(idx)
    unmatched_indices = still_unmatched

    # Stage 2: Exact email match (confidence 0.95)
    still_unmatched = []
    for idx in unmatched_indices:
        cs = contact_sources[idx]
        norm_em = normalize_email(cs.email) if cs.email else ''
        if norm_em:
            conn_id = email_map.get(norm_em)
            if conn_id:
                _mark_matched(cs, conn_id, 'exact_email', 0.95)
                continue
        still_unmatched.append(idx)
    unmatched_indices = still_unmatched

    # Stage 3: Fuzzy name+company match (threshold 0.85)
    still_unmatched = []
    for idx in unmatched_indices:
        cs = contact_sources[idx]
        cs_name = _build_full_name(cs.first_name, cs.last_name)
        if cs_name and cs.company and name_entries:
            match = _fuzzy_match(cs_name, cs.company, name_entries)
            if match:
                conn_id, score = match
                _mark_matched(cs, conn_id, 'fuzzy_name_company', score / 100.0)
                continue
        # Stage 4: Unmatched → new
        cs.dedup_status = 'new'
        cs.dedup_method = None
        cs.dedup_confidence = None
        still_unmatched.append(idx)
    unmatched_indices = still_unmatched


def _mark_matched(cs: ContactSourceEntity, conn_id: str, method: str, confidence: float) -> None:
    cs.dedup_status = 'matched'
    cs.dedup_method = method
    cs.dedup_confidence = confidence
    cs.connection_id = conn_id


def _build_full_name(first: str | None, last: str | None) -> str:
    parts = [p for p in (first, last) if p and p.strip()]
    return ' '.join(parts).strip()


def _fuzzy_match(
    name: str,
    company: str,
    entries: list[ConnectionLookupEntry],
) -> tuple[str, float] | None:
    """Find best fuzzy match. Returns (connection_id, name_score) or None."""
    best_id: str | None = None
    best_score: float = 0.0

    for entry in entries:
        if not entry.full_name:
            continue
        name_score = token_sort_ratio(name, entry.full_name)
        if name_score < 85:
            continue
        # Company must also match
        if entry.company:
            company_score = token_sort_ratio(company, entry.company)
            if company_score < 80:
                continue
        else:
            continue  # Can't match without company
        if name_score > best_score:
            best_score = name_score
            best_id = entry.connection_id

    if best_id and best_score >= 85:
        return best_id, best_score
    return None
