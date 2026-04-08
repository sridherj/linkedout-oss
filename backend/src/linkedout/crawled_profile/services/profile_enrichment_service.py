# SPDX-License-Identifier: Apache-2.0
import json
from datetime import date as date_type
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from linkedout.company.entities.company_entity import CompanyEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.crawled_profile.repositories.crawled_profile_repository import CrawledProfileRepository
from linkedout.crawled_profile.schemas.crawled_profile_api_schema import (
    EnrichProfileRequestSchema, EnrichProfileResponseSchema,
)
from linkedout.education.entities.education_entity import EducationEntity
from linkedout.experience.entities.experience_entity import ExperienceEntity
from linkedout.profile_skill.entities.profile_skill_entity import ProfileSkillEntity
from linkedout.role_alias.repositories.role_alias_repository import RoleAliasRepository
from shared.utils.company_resolver import resolve_company
from shared.utils.company_matcher import CompanyMatcher
from utilities.llm_manager.embedding_factory import get_embedding_column_name, get_embedding_provider
from utilities.llm_manager.embedding_provider import EmbeddingProvider, build_embedding_text
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")

FAILED_EMBEDDINGS_PATH = Path('data/failed_embeddings.jsonl')


class ProfileEnrichmentService:
    """Owns the full "make profile searchable" lifecycle.

    Responsibilities:
    - Structured rows (delete-then-create): experience, education, skill
    - Company resolution via CompanyMatcher
    - Role alias resolution (seniority_level, function_area) per experience
    - search_vector rebuild
    - Synchronous embedding generation (Q2)
    - JSONL failure logging for failed embeddings (Q2)
    """

    def __init__(self, session: Session, embedding_provider: Optional[EmbeddingProvider] = None):
        self._session = session
        self._repository = CrawledProfileRepository(session)
        self._embedding_provider = embedding_provider
        self._role_alias_repo = RoleAliasRepository(session)
        self._company_matcher = CompanyMatcher()
        self._company_by_canonical: dict[str, CompanyEntity] = {}
        self._preload_companies()

    def _preload_companies(self) -> None:
        """Load existing companies into matcher for dedup."""
        companies = self._session.execute(select(CompanyEntity)).scalars().all()
        for co in companies:
            self._company_matcher.match_or_create(
                company_name=co.canonical_name,
                linkedin_url=co.linkedin_url,
                universal_name=co.universal_name,
            )
            self._company_by_canonical[co.canonical_name] = co

    def enrich(self, profile_id: str, request: EnrichProfileRequestSchema) -> EnrichProfileResponseSchema:
        """Write experience/education/skill rows for a profile.

        Owns the full "make profile searchable" lifecycle:
        - Structured rows (delete-then-create)
        - Company resolution
        - Role alias resolution (seniority_level, function_area) per experience
        - search_vector rebuild
        - Synchronous embedding generation
        """
        session = self._session

        # 1. Verify profile exists (FOR UPDATE serializes concurrent enrichments)
        profile = session.query(CrawledProfileEntity).filter(
            CrawledProfileEntity.id == profile_id,
        ).with_for_update().one_or_none()
        if not profile:
            raise ValueError(f'CrawledProfile not found: {profile_id}')

        # 2. Bulk delete existing rows (idempotent re-enrichment)
        session.execute(ExperienceEntity.__table__.delete().where(
            ExperienceEntity.crawled_profile_id == profile_id))
        session.execute(EducationEntity.__table__.delete().where(
            EducationEntity.crawled_profile_id == profile_id))
        session.execute(ProfileSkillEntity.__table__.delete().where(
            ProfileSkillEntity.crawled_profile_id == profile_id))

        # 3. Create experiences
        for exp in request.experiences:
            company_id = resolve_company(
                session, self._company_matcher, self._company_by_canonical,
                exp.company_name, exp.company_linkedin_url, exp.company_universal_name,
            )

            # Compute date fields from year/month
            start_date = date_type(exp.start_year, exp.start_month or 1, 1) if exp.start_year else None
            end_date = None
            if exp.end_year and not exp.is_current:
                end_date = date_type(exp.end_year, exp.end_month or 1, 1)

            # Q5: Role alias lookup for seniority + function area
            seniority_level = None
            function_area = None
            if exp.position:
                alias = self._role_alias_repo.get_by_alias_title(exp.position)
                if alias:
                    seniority_level = alias.seniority_level
                    function_area = alias.function_area

            session.add(ExperienceEntity(
                crawled_profile_id=profile_id,
                position=exp.position,
                company_name=exp.company_name,
                company_id=company_id,
                company_linkedin_url=exp.company_linkedin_url,
                employment_type=exp.employment_type,
                start_date=start_date,
                start_year=exp.start_year,
                start_month=exp.start_month,
                end_date=end_date,
                end_year=exp.end_year,
                end_month=exp.end_month,
                end_date_text='Present' if exp.is_current else None,
                is_current=exp.is_current if exp.is_current else None,
                seniority_level=seniority_level,
                function_area=function_area,
                location=exp.location,
                description=exp.description,
            ))

        # 4. Create educations
        for edu in request.educations:
            session.add(EducationEntity(
                crawled_profile_id=profile_id,
                school_name=edu.school_name,
                school_linkedin_url=edu.school_linkedin_url,
                degree=edu.degree,
                field_of_study=edu.field_of_study,
                start_year=edu.start_year,
                end_year=edu.end_year,
                description=edu.description,
            ))

        # 5. Create skills (deduplicated)
        seen: set[str] = set()
        for skill_name in request.skills:
            if not skill_name or skill_name in seen:
                continue
            seen.add(skill_name)
            session.add(ProfileSkillEntity(
                crawled_profile_id=profile_id,
                skill_name=skill_name,
                endorsement_count=0,
            ))

        # 6. Set has_enriched_data flag (Q9: always true after attempt)
        profile.has_enriched_data = True

        # 7. Q1: Rebuild search_vector (enrich() owns this)
        parts = []
        if profile.full_name: parts.append(profile.full_name)
        if profile.headline: parts.append(profile.headline)
        if profile.about: parts.append(profile.about)
        for exp in request.experiences:
            if exp.company_name: parts.append(exp.company_name)
            if exp.position: parts.append(exp.position)
        profile.search_vector = ' '.join(parts) if parts else None

        session.flush()

        # 8. Q2: Synchronous embedding generation + JSONL failure logging
        self._generate_embedding(profile, request)

        return EnrichProfileResponseSchema(
            experiences_created=len(request.experiences),
            educations_created=len(request.educations),
            skills_created=len(seen),
        )

    def _generate_embedding(self, profile: CrawledProfileEntity, request: EnrichProfileRequestSchema) -> None:
        """Generate embedding synchronously. On failure, append to JSONL for retry."""
        if not self._embedding_provider:
            logger.debug('No embedding provider — skipping embedding generation')
            return

        exp_dicts = [
            {'company_name': e.company_name or '', 'title': e.position or ''}
            for e in request.experiences
        ]
        profile_dict = {
            'full_name': profile.full_name,
            'headline': profile.headline,
            'about': profile.about,
            'experiences': exp_dicts,
        }
        text = build_embedding_text(profile_dict)
        if not text.strip():
            return

        try:
            provider = self._embedding_provider
            vector = provider.embed_single(text)
            column_name = get_embedding_column_name(provider)
            setattr(profile, column_name, vector)
            profile.embedding_model = provider.model_name()
            profile.embedding_dim = provider.dimension()
            from datetime import datetime, timezone
            profile.embedding_updated_at = datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f'Embedding generation failed for {profile.id}: {e}')
            self._log_failed_embedding(profile.id, str(e))

    def _log_failed_embedding(self, profile_id: str, error: str) -> None:
        """Append failed embedding to JSONL file for later retry."""
        from datetime import datetime, timezone
        entry = {
            'profile_id': profile_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': error,
        }
        try:
            FAILED_EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(FAILED_EMBEDDINGS_PATH, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            logger.error(f'Failed to log embedding failure: {e}')
