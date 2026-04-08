# SPDX-License-Identifier: Apache-2.0
"""PostEnrichmentService — processes Apify results into relational data."""
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from linkedout.company.entities.company_entity import CompanyEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.crawled_profile.schemas.crawled_profile_api_schema import (
    EnrichEducationItem,
    EnrichExperienceItem,
    EnrichProfileRequestSchema,
)
from linkedout.crawled_profile.services.profile_enrichment_service import ProfileEnrichmentService
from linkedout.enrichment_event.entities.enrichment_event_entity import EnrichmentEventEntity
from linkedout.role_alias.repositories.role_alias_repository import RoleAliasRepository
from shared.utils.company_matcher import CompanyMatcher
from shared.utils.company_resolver import resolve_company
from shared.utils.date_parsing import parse_month_name
from utilities.llm_manager.embedding_provider import EmbeddingProvider
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="enrichment")


class PostEnrichmentService:
    """Processes Apify enrichment results into the database.

    Called synchronously from the enrichment controller after Apify returns data.
    Delegates structured row creation to ProfileEnrichmentService.enrich().
    """

    def __init__(self, session: Session, embedding_provider: Optional[EmbeddingProvider] = None):
        self._session = session
        self._embedding_provider = embedding_provider
        self._company_matcher = CompanyMatcher()
        self._role_alias_repo = RoleAliasRepository(session)
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
        # Also store id mapping: canonical_name -> company entity
        self._company_by_canonical: dict[str, CompanyEntity] = {
            co.canonical_name: co for co in companies
        }

    def process_enrichment_result(
        self,
        apify_data: dict,
        enrichment_event_id: str,
        linkedin_url: str,
    ) -> None:
        """Process a single Apify profile result.

        1. Race-condition re-check (cache)
        2. Update/create crawled profile
        3. Delegate structured rows + embedding + search_vector to enrich()
        4. Update enrichment event to completed
        """
        # 1. Race condition guard — re-check cache
        profile = self._session.execute(
            select(CrawledProfileEntity).where(
                CrawledProfileEntity.linkedin_url == linkedin_url
            )
        ).scalar_one_or_none()

        if profile and profile.has_enriched_data:
            now = datetime.now(timezone.utc)
            if profile.last_crawled_at:
                last_crawled = profile.last_crawled_at
                if hasattr(last_crawled, 'tzinfo') and last_crawled.tzinfo is None:
                    from datetime import timezone as tz
                    last_crawled = last_crawled.replace(tzinfo=tz.utc)
                days_since = (now - last_crawled).days
                if days_since < 90:
                    logger.info(f'Race condition: {linkedin_url} already enriched {days_since}d ago')
                    self._update_enrichment_event(enrichment_event_id, 'cache_hit', 0.0)
                    return

        if not profile:
            logger.warning(f'No crawled_profile for {linkedin_url} — creating stub')
            profile = CrawledProfileEntity(
                linkedin_url=linkedin_url,
                data_source='apify',
            )
            self._session.add(profile)
            self._session.flush()

        # 2. Update crawled profile with Apify data
        self._update_crawled_profile(profile, apify_data)

        # 3. Delegate structured rows, search_vector, and embedding to enrich()
        enrich_request = self._to_enrich_schema(apify_data)
        enrichment_service = ProfileEnrichmentService(self._session, self._embedding_provider)
        enrichment_service.enrich(profile.id, enrich_request)

        # 4. Update enrichment event
        self._update_enrichment_event(enrichment_event_id, 'completed', 0.004)

        self._session.flush()
        logger.info(f'Enrichment complete for {linkedin_url} (profile={profile.id})')

    def _to_enrich_schema(self, apify_data: dict) -> EnrichProfileRequestSchema:
        """Transform Apify JSON into the canonical EnrichProfileRequestSchema."""
        # Experiences
        experiences = []
        for exp in (apify_data.get('experience', []) or []):
            start_date_obj = exp.get('startDate', {}) or {}
            end_date_obj = exp.get('endDate', {}) or {}

            start_month = self._parse_month_field(start_date_obj.get('month'))
            end_month = self._parse_month_field(end_date_obj.get('month'))

            end_date_text = end_date_obj.get('text')
            is_current = (end_date_text or '').strip().lower() == 'present'

            experiences.append(EnrichExperienceItem(
                position=exp.get('position'),
                company_name=exp.get('companyName'),
                company_linkedin_url=exp.get('companyLinkedinUrl'),
                company_universal_name=exp.get('companyUniversalName'),
                employment_type=exp.get('employmentType'),
                start_year=start_date_obj.get('year') if isinstance(start_date_obj.get('year'), int) else None,
                start_month=start_month,
                end_year=end_date_obj.get('year') if isinstance(end_date_obj.get('year'), int) else None,
                end_month=end_month,
                is_current=is_current if is_current else None,
                location=exp.get('location'),
                description=exp.get('description'),
            ))

        # Educations
        educations = []
        for edu in (apify_data.get('education', []) or []):
            start_date_obj = edu.get('startDate', {}) or {}
            end_date_obj = edu.get('endDate', {}) or {}

            educations.append(EnrichEducationItem(
                school_name=edu.get('schoolName'),
                school_linkedin_url=edu.get('schoolLinkedinUrl'),
                degree=edu.get('degree'),
                field_of_study=edu.get('fieldOfStudy'),
                start_year=start_date_obj.get('year') if isinstance(start_date_obj.get('year'), int) else None,
                end_year=end_date_obj.get('year') if isinstance(end_date_obj.get('year'), int) else None,
                description=edu.get('description'),
            ))

        # Skills — merge skills (dict with .name) + topSkills (strings)
        skills: list[str] = []
        seen: set[str] = set()
        for skill in (apify_data.get('skills', []) or []):
            skill_name = skill.get('name') if isinstance(skill, dict) else str(skill)
            if skill_name and skill_name not in seen:
                seen.add(skill_name)
                skills.append(skill_name)
        for skill_name in (apify_data.get('topSkills', []) or []):
            if skill_name and skill_name not in seen:
                seen.add(skill_name)
                skills.append(skill_name)

        return EnrichProfileRequestSchema(
            experiences=experiences,
            educations=educations,
            skills=skills,
        )

    @staticmethod
    def _parse_month_field(month_val) -> Optional[int]:
        """Parse a month value that may be int or string."""
        if isinstance(month_val, int):
            return month_val
        if isinstance(month_val, str):
            return parse_month_name(month_val)
        return None

    def _update_crawled_profile(self, profile: CrawledProfileEntity, data: dict) -> None:
        """Map Apify fields to crawled_profile columns."""
        profile.public_identifier = data.get('publicIdentifier') or profile.public_identifier
        profile.first_name = data.get('firstName') or profile.first_name
        profile.last_name = data.get('lastName') or profile.last_name

        first = data.get('firstName', '') or ''
        last = data.get('lastName', '') or ''
        if first or last:
            profile.full_name = f'{first} {last}'.strip()

        profile.headline = data.get('headline') or profile.headline
        profile.about = data.get('about') or profile.about

        location = data.get('location', {}) or {}
        parsed_loc = location.get('parsed', {}) or {}
        profile.location_city = parsed_loc.get('city') or profile.location_city
        profile.location_state = parsed_loc.get('state') or profile.location_state
        profile.location_country = parsed_loc.get('country') or profile.location_country
        profile.location_country_code = parsed_loc.get('countryCode') or profile.location_country_code
        profile.location_raw = location.get('linkedinText') or profile.location_raw

        if data.get('connectionsCount') is not None:
            profile.connections_count = data['connectionsCount']
        if data.get('followerCount') is not None:
            profile.follower_count = data['followerCount']
        if data.get('openToWork') is not None:
            profile.open_to_work = data['openToWork']
        if data.get('premium') is not None:
            profile.premium = data['premium']

        # Current position from currentPosition array
        current_positions = data.get('currentPosition', []) or []
        if current_positions:
            cp = current_positions[0]
            profile.current_company_name = cp.get('companyName') or profile.current_company_name
            # Resolve company using shared utility
            company_id = resolve_company(
                self._session, self._company_matcher, self._company_by_canonical,
                cp.get('companyName'), cp.get('companyLinkedinUrl'),
            )
            if company_id:
                profile.company_id = company_id

        # Current position title from experience
        experiences = data.get('experience', []) or []
        for exp in experiences:
            end_date = exp.get('endDate', {}) or {}
            if end_date.get('text', '').strip().lower() == 'present':
                profile.current_position = exp.get('position') or profile.current_position
                break

        # Seniority / function area from role_alias lookup
        if profile.current_position:
            alias = self._role_alias_repo.get_by_alias_title(profile.current_position)
            if alias:
                profile.seniority_level = alias.seniority_level
                profile.function_area = alias.function_area

        # Profile image
        profile_pic = data.get('profilePicture', {}) or {}
        if profile_pic.get('url'):
            profile.profile_image_url = profile_pic['url']

        profile.raw_profile = json.dumps(data)
        profile.has_enriched_data = True
        profile.last_crawled_at = datetime.now(timezone.utc)
        profile.data_source = 'apify'

    def _update_enrichment_event(self, event_id: str, event_type: str, cost: float) -> None:
        """Update an enrichment event status."""
        event = self._session.execute(
            select(EnrichmentEventEntity).where(EnrichmentEventEntity.id == event_id)
        ).scalar_one_or_none()
        if event:
            event.event_type = event_type
            event.cost_estimate_usd = cost
