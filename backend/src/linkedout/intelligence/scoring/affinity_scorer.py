# SPDX-License-Identifier: Apache-2.0
"""Affinity scoring engine for connections.

Computes affinity scores based on source count, recency, career overlap,
and embedding similarity, then assigns Dunbar tiers by rank within each
user's connections.
"""
from datetime import date, datetime, timezone
from math import log2
from typing import Optional

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from linkedout.company.entities.company_entity import CompanyEntity
from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.contact_source.entities.contact_source_entity import ContactSourceEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.experience.entities.experience_entity import ExperienceEntity
from organization.entities.app_user_entity import AppUserEntity
from shared.config.settings import get_config
from utilities.llm_manager.embedding_factory import get_embedding_column_name, get_embedding_provider

AFFINITY_VERSION = 3

# Source count normalization (data-format constant, not user-tunable)
SOURCE_COUNT_MAP = {1: 0.2, 2: 0.5, 3: 0.8}

DUNBAR_DEFAULT = 'acquaintance'

# External contact source types that contribute to warmth signal
EXTERNAL_SOURCE_TYPES = {'google_contacts_job', 'gmail_email_only', 'contacts_phone'}

SENIORITY_DEFAULT_BOOST = 1.0  # fallback when seniority_level is missing


def size_factor(employee_count: Optional[int] = None) -> float:
    """Company-size dampening: smaller companies produce larger factors.

    Formula: 1.0 / log2((employee_count or 500) + 2)
    Defaults to 500 (mid-size assumption) when employee_count is None or 0.
    """
    return 1.0 / log2((employee_count or 500) + 2)


def overlap_months(
    start_a: Optional[date], end_a: Optional[date],
    start_b: Optional[date], end_b: Optional[date],
) -> float:
    """Compute months of concurrent employment between two date ranges.

    Returns 0.0 if either start_date is None. Treats None end_date as today.
    """
    if start_a is None or start_b is None:
        return 0.0
    today = date.today()
    ea, eb = end_a or today, end_b or today
    ov_start = max(start_a, start_b)
    ov_end = min(ea, eb)
    if ov_end <= ov_start:
        return 0.0
    return float((ov_end.year - ov_start.year) * 12 + (ov_end.month - ov_start.month))


def _normalize_source_count(count: int) -> float:
    if count <= 0:
        return 0.0
    return SOURCE_COUNT_MAP.get(count, 1.0)


def _compute_recency(connected_at: Optional[date], reference_date: Optional[date] = None) -> float:
    if connected_at is None:
        return 0.0
    ref = reference_date or date.today()
    months_elapsed = (ref - connected_at).days * 12 / 365.25
    for threshold_months, score in get_config().scoring.recency_thresholds:
        if months_elapsed < threshold_months:
            return float(score)
    return 0.2


def _seniority_boost(user_seniority: Optional[str], conn_seniority: Optional[str]) -> float:
    """Return the seniority boost multiplier for a shared-company pair.

    Uses the higher seniority between user and connection. Defaults to 1.0 for unknown levels.
    """
    boosts = get_config().scoring.seniority_boosts
    u_boost = boosts.get(user_seniority, SENIORITY_DEFAULT_BOOST) if user_seniority else SENIORITY_DEFAULT_BOOST
    c_boost = boosts.get(conn_seniority, SENIORITY_DEFAULT_BOOST) if conn_seniority else SENIORITY_DEFAULT_BOOST
    return max(u_boost, c_boost)


def _compute_career_overlap(
    connection_experiences: list[dict],
    user_experiences: list[dict],
    company_sizes: dict[str, int],
) -> float:
    """Compute career overlap with company-size normalization, seniority boost, and temporal overlap.

    For each matching company pair, computes overlap_months * size_factor * seniority_boost,
    sums all, then caps with min(total / 36.0, 1.0).

    Experience dicts may include 'seniority_level' (str or None). When multiple roles exist
    at the same company, the highest seniority across overlapping roles is used.
    """
    if not connection_experiences or not user_experiences:
        return 0.0
    total = 0.0
    for user_exp in user_experiences:
        for conn_exp in connection_experiences:
            u_cid = user_exp.get('company_id')
            c_cid = conn_exp.get('company_id')
            if u_cid is None or c_cid is None or u_cid != c_cid:
                continue
            months = overlap_months(
                user_exp.get('start_date'), user_exp.get('end_date'),
                conn_exp.get('start_date'), conn_exp.get('end_date'),
            )
            boost = _seniority_boost(
                user_exp.get('seniority_level'),
                conn_exp.get('seniority_level'),
            )
            total += months * size_factor(company_sizes.get(u_cid)) * boost
    return min(total / float(get_config().scoring.career_normalization_months), 1.0)


def _compute_affinity(
    source_count_norm: float, recency: float, career_overlap: float,
    external_contact: float, embedding_similarity: float,
) -> float:
    scoring = get_config().scoring
    raw = (
        career_overlap * scoring.weight_career_overlap
        + external_contact * scoring.weight_external_contact
        + embedding_similarity * scoring.weight_embedding_similarity
        + source_count_norm * scoring.weight_source_count
        + recency * scoring.weight_recency
    )
    return round(raw * 100, 1)


def _assign_dunbar_tier(rank: int) -> str:
    scoring = get_config().scoring
    tiers = [
        (scoring.dunbar_inner_circle, 'inner_circle'),
        (scoring.dunbar_active, 'active'),
        (scoring.dunbar_familiar, 'familiar'),
    ]
    for cutoff, tier in tiers:
        if rank <= cutoff:
            return tier
    return DUNBAR_DEFAULT


def _compute_external_contact_score(contact_sources: list[dict]) -> float:
    """Score external contact warmth. Phone=1.0, email=0.7, highest tier wins (no stacking)."""
    external = [cs for cs in contact_sources if cs.get('source_type') in EXTERNAL_SOURCE_TYPES]
    if not external:
        return 0.0
    scores = get_config().scoring.external_contact_scores
    if any(cs.get('phone') for cs in external):
        return scores.get('phone', 1.0)
    if any(cs.get('email') for cs in external):
        return scores.get('email', 0.7)
    return 0.0


class AffinityScorer:
    """Computes affinity scores and Dunbar tiers for user connections."""

    def __init__(self, session: Session):
        self._session = session

    def _get_user_experiences(self, app_user_id: str) -> list[dict]:
        """Get experience dicts from the user's own crawled profile.

        Requires app_user.own_crawled_profile_id to be set. Returns empty list if not configured.
        """
        app_user = self._session.get(AppUserEntity, app_user_id)
        if app_user is None or app_user.own_crawled_profile_id is None:
            return []
        stmt = (
            select(
                ExperienceEntity.company_id,
                ExperienceEntity.start_date,
                ExperienceEntity.end_date,
                ExperienceEntity.seniority_level,
            )
            .where(
                ExperienceEntity.crawled_profile_id == app_user.own_crawled_profile_id,
                ExperienceEntity.company_id.isnot(None),
            )
        )
        return [
            {'company_id': row[0], 'start_date': row[1], 'end_date': row[2], 'seniority_level': row[3]}
            for row in self._session.execute(stmt).all()
        ]

    def _batch_fetch_external_contacts(self, connection_ids: list[str]) -> dict[str, list[dict]]:
        """Pre-fetch external contact sources for connections in ONE query."""
        if not connection_ids:
            return {}
        stmt = (
            select(
                ContactSourceEntity.connection_id,
                ContactSourceEntity.source_type,
                ContactSourceEntity.phone,
                ContactSourceEntity.email,
            )
            .where(
                ContactSourceEntity.connection_id.in_(connection_ids),
                ContactSourceEntity.source_type.in_(EXTERNAL_SOURCE_TYPES),
                ContactSourceEntity.dedup_status == 'matched',
            )
        )
        result: dict[str, list[dict]] = {}
        for conn_id, source_type, phone, email in self._session.execute(stmt).all():
            result.setdefault(conn_id, []).append({
                'source_type': source_type,
                'phone': phone,
                'email': email,
            })
        return result

    def _batch_fetch_connection_experiences(self, app_user_id: str) -> dict[str, list[dict]]:
        """Pre-fetch experience dicts (company_id, start_date, end_date, seniority_level) for all user connections."""
        stmt = (
            select(
                ConnectionEntity.id,
                ExperienceEntity.company_id,
                ExperienceEntity.start_date,
                ExperienceEntity.end_date,
                ExperienceEntity.seniority_level,
            )
            .join(CrawledProfileEntity, ConnectionEntity.crawled_profile_id == CrawledProfileEntity.id)
            .join(ExperienceEntity, ExperienceEntity.crawled_profile_id == CrawledProfileEntity.id)
            .where(
                ConnectionEntity.app_user_id == app_user_id,
                ExperienceEntity.company_id.isnot(None),
            )
        )
        result: dict[str, list[dict]] = {}
        for conn_id, company_id, start_dt, end_dt, seniority in self._session.execute(stmt).all():
            result.setdefault(conn_id, []).append({
                'company_id': company_id,
                'start_date': start_dt,
                'end_date': end_dt,
                'seniority_level': seniority,
            })
        return result

    def _batch_fetch_company_sizes(self, company_ids: set[str]) -> dict[str, int]:
        """Fetch estimated_employee_count for a set of company IDs."""
        if not company_ids:
            return {}
        stmt = (
            select(CompanyEntity.id, CompanyEntity.estimated_employee_count)
            .where(CompanyEntity.id.in_(company_ids))
        )
        return {row[0]: row[1] for row in self._session.execute(stmt).all()}

    def _get_embedding_column(self) -> str:
        """Return the active embedding column name based on configured provider."""
        provider = get_embedding_provider()
        return get_embedding_column_name(provider)

    def _get_user_embedding(self, app_user_id: str) -> Optional[list[float]]:
        """Get the embedding vector for the user's own crawled profile.

        Returns None if the user has no own_crawled_profile_id or the profile has no embedding
        for the active provider.
        """
        app_user = self._session.get(AppUserEntity, app_user_id)
        if app_user is None or app_user.own_crawled_profile_id is None:
            return None
        profile = self._session.get(CrawledProfileEntity, app_user.own_crawled_profile_id)
        if profile is None:
            return None
        column_name = self._get_embedding_column()
        return getattr(profile, column_name, None)

    def _batch_fetch_embedding_similarities(
        self, app_user_id: str, user_embedding: list[float]
    ) -> dict[str, float]:
        """Compute cosine similarity between user embedding and all connection embeddings DB-side.

        Uses pgvector's <=> (cosine distance) operator: similarity = 1 - distance.
        Returns dict keyed by connection_id. Connections without embeddings get 0.0.
        """
        col = self._get_embedding_column()
        # col is one of two known values from application config, not user input
        stmt = text(f"""
            SELECT c.id, 1 - (cp.{col} <=> :user_embedding) AS similarity
            FROM connection c
            JOIN crawled_profile cp ON c.crawled_profile_id = cp.id
            WHERE c.app_user_id = :app_user_id
              AND cp.{col} IS NOT NULL
        """)
        # Format as pgvector-compatible string: [0.1,0.2,...] not numpy repr
        if hasattr(user_embedding, 'tolist'):
            emb_list = user_embedding.tolist()
        else:
            emb_list = list(user_embedding)
        emb_str = '[' + ','.join(str(v) for v in emb_list) + ']'
        rows = self._session.execute(
            stmt, {'app_user_id': app_user_id, 'user_embedding': emb_str}
        ).all()
        return {row[0]: max(0.0, float(row[1])) for row in rows}

    def compute_for_user(self, app_user_id: str, reference_date: Optional[date] = None) -> int:
        """Recompute affinity for all connections of a user. Returns count updated."""
        # Fetch all connections for this user
        connections = self._session.execute(
            select(ConnectionEntity).where(ConnectionEntity.app_user_id == app_user_id)
        ).scalars().all()

        if not connections:
            return 0

        # Batch fetch career data, external contacts, and embeddings
        user_experiences = self._get_user_experiences(app_user_id)
        conn_experiences = self._batch_fetch_connection_experiences(app_user_id)
        conn_ids = [conn.id for conn in connections]
        ext_contacts = self._batch_fetch_external_contacts(conn_ids)

        # Fetch user embedding and batch-compute similarities
        user_embedding = self._get_user_embedding(app_user_id)
        embedding_sims: dict[str, float] = {}
        if user_embedding is not None:
            embedding_sims = self._batch_fetch_embedding_similarities(app_user_id, user_embedding)

        # Collect all company IDs for size lookup
        all_company_ids: set[str] = set()
        for exp in user_experiences:
            if exp['company_id']:
                all_company_ids.add(exp['company_id'])
        for exps in conn_experiences.values():
            for exp in exps:
                if exp['company_id']:
                    all_company_ids.add(exp['company_id'])
        company_sizes = self._batch_fetch_company_sizes(all_company_ids)

        # Compute signals and scores
        now = datetime.now(timezone.utc)
        scored: list[tuple[ConnectionEntity, float, float, float, float, float, float]] = []

        for conn in connections:
            src_count = len(conn.sources) if conn.sources else 0
            src_norm = _normalize_source_count(src_count)
            recency = _compute_recency(conn.connected_at, reference_date)
            career = _compute_career_overlap(
                conn_experiences.get(conn.id, []), user_experiences, company_sizes
            )
            ext_contact = _compute_external_contact_score(ext_contacts.get(conn.id, []))
            emb_sim = embedding_sims.get(conn.id, 0.0)
            score = _compute_affinity(src_norm, recency, career, ext_contact, emb_sim)
            scored.append((conn, score, src_norm, recency, career, ext_contact, emb_sim))

        # Sort by score descending for Dunbar tier assignment.
        # Tiebreak by connection ID (ascending) for deterministic ordering.
        scored.sort(key=lambda x: (-x[1], x[0].id))

        # Bulk update
        updates = []
        for rank, (conn, score, src_norm, recency, career, ext_contact, emb_sim) in enumerate(scored, 1):
            updates.append({
                'id': conn.id,
                'affinity_score': score,
                'affinity_source_count': src_norm,
                'affinity_recency': recency,
                'affinity_career_overlap': career,
                'affinity_mutual_connections': 0.0,
                'affinity_external_contact': ext_contact,
                'affinity_embedding_similarity': emb_sim,
                'affinity_computed_at': now,
                'affinity_version': AFFINITY_VERSION,
                'dunbar_tier': _assign_dunbar_tier(rank),
            })

        if updates:
            self._session.execute(
                update(ConnectionEntity),
                updates,
            )
            self._session.flush()

        return len(updates)

    def compute_for_connection(self, connection_id: str, reference_date: Optional[date] = None) -> float:
        """Recompute affinity for a single connection. Returns new score.

        Note: This does NOT reassign Dunbar tiers (that requires full user recomputation).
        """
        conn = self._session.get(ConnectionEntity, connection_id)
        if conn is None:
            raise ValueError(f"Connection {connection_id} not found")

        user_experiences = self._get_user_experiences(conn.app_user_id)

        # Fetch this connection's experiences
        stmt = (
            select(
                ExperienceEntity.company_id,
                ExperienceEntity.start_date,
                ExperienceEntity.end_date,
                ExperienceEntity.seniority_level,
            )
            .join(CrawledProfileEntity, ExperienceEntity.crawled_profile_id == CrawledProfileEntity.id)
            .where(
                CrawledProfileEntity.id == conn.crawled_profile_id,
                ExperienceEntity.company_id.isnot(None),
            )
        )
        conn_experiences = [
            {'company_id': row[0], 'start_date': row[1], 'end_date': row[2], 'seniority_level': row[3]}
            for row in self._session.execute(stmt).all()
        ]

        # Collect company IDs for size lookup
        all_company_ids: set[str] = set()
        for exp in user_experiences:
            if exp['company_id']:
                all_company_ids.add(exp['company_id'])
        for exp in conn_experiences:
            if exp['company_id']:
                all_company_ids.add(exp['company_id'])
        company_sizes = self._batch_fetch_company_sizes(all_company_ids)

        src_count = len(conn.sources) if conn.sources else 0
        src_norm = _normalize_source_count(src_count)
        recency = _compute_recency(conn.connected_at, reference_date)
        career = _compute_career_overlap(conn_experiences, user_experiences, company_sizes)
        ext_contacts = self._batch_fetch_external_contacts([connection_id])
        ext_contact = _compute_external_contact_score(ext_contacts.get(connection_id, []))

        # Compute embedding similarity
        user_embedding = self._get_user_embedding(conn.app_user_id)
        if user_embedding is not None:
            emb_sims = self._batch_fetch_embedding_similarities(conn.app_user_id, user_embedding)
            emb_sim = emb_sims.get(connection_id, 0.0)
        else:
            emb_sim = 0.0

        score = _compute_affinity(src_norm, recency, career, ext_contact, emb_sim)

        conn.affinity_score = score
        conn.affinity_source_count = src_norm
        conn.affinity_recency = recency
        conn.affinity_career_overlap = career
        conn.affinity_mutual_connections = 0.0
        conn.affinity_external_contact = ext_contact
        conn.affinity_embedding_similarity = emb_sim
        conn.affinity_computed_at = datetime.now(timezone.utc)
        conn.affinity_version = AFFINITY_VERSION
        self._session.flush()

        return score
