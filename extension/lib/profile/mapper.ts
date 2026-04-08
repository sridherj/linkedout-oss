// SPDX-License-Identifier: Apache-2.0
/** VoyagerProfile → backend-compatible payload. */

import { getConfigSync } from '../config';
import { normalizeLinkedinUrl } from './url';
import type { VoyagerProfile, VoyagerCompany } from '../voyager/types';
import type { CrawledProfilePayload, EnrichProfilePayload } from '../backend/types';

/**
 * Map a parsed Voyager profile to the backend CreateCrawledProfileRequestSchema.
 */
export function toCrawledProfilePayload(
  profile: VoyagerProfile,
  profileId: string,
): CrawledProfilePayload {
  // Derive current position from first position without an endDate
  const currentPos = profile.positions.find((p) => !p.endDate);

  const linkedinUrl =
    normalizeLinkedinUrl(
      `https://www.linkedin.com/in/${profileId}`,
    ) ?? `https://www.linkedin.com/in/${profileId}`;

  return {
    linkedin_url: linkedinUrl,
    public_identifier: profileId,
    first_name: profile.firstName || null,
    last_name: profile.lastName || null,
    full_name:
      [profile.firstName, profile.lastName].filter(Boolean).join(' ') || null,
    headline: profile.headline || null,
    about: profile.summary || null,
    location_city: profile.geo?.city ?? null,
    location_state: profile.geo?.state ?? null,
    location_country: profile.geo?.country ?? null,
    location_country_code: profile.geo?.countryCode ?? null,
    location_raw: profile.geo?.fullName ?? profile.locationName ?? null,
    connections_count: profile.connectionsCount ?? null,
    follower_count: profile.followerCount ?? null,
    open_to_work: profile.openToWork || null,
    premium: profile.premium || null,
    current_company_name: currentPos?.companyName || null,
    current_position: currentPos?.title || null,
    profile_image_url: profile.profilePicture || null,
    source_app_user_id: getConfigSync().userId,
    data_source: 'extension',
    last_crawled_at: new Date().toISOString(),
    raw_profile: JSON.stringify(profile),
  };
}

// ── Enrichment helpers ──────────────────────────────────────

/** Extract year from "2022-09" or "2022". Returns null for null/empty. */
export function parseYear(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const year = parseInt(dateStr.split('-')[0], 10);
  return Number.isNaN(year) ? null : year;
}

/** Extract month from "2022-09". Returns null for "2022" or null/empty. */
export function parseMonth(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const parts = dateStr.split('-');
  if (parts.length < 2) return null;
  const month = parseInt(parts[1], 10);
  return Number.isNaN(month) ? null : month;
}

/** Resolve companyUrn to its VoyagerCompany entry. */
function resolveCompany(
  companyUrn: string | null,
  companies: VoyagerCompany[],
): VoyagerCompany | undefined {
  if (!companyUrn) return undefined;
  return companies.find((c) => c.entityUrn === companyUrn);
}

/**
 * Map a parsed Voyager profile to the backend EnrichProfilePayload.
 */
export function toEnrichPayload(profile: VoyagerProfile): EnrichProfilePayload {
  const experiences = profile.positions.map((pos) => {
    const company = resolveCompany(pos.companyUrn, profile.companies);
    return {
      position: pos.title || null,
      company_name: pos.companyName || null,
      company_linkedin_url: company?.url ?? null,
      company_universal_name: company?.universalName ?? null,
      start_year: parseYear(pos.startDate),
      start_month: parseMonth(pos.startDate),
      end_year: parseYear(pos.endDate),
      end_month: parseMonth(pos.endDate),
      is_current: !pos.endDate ? true : null,
      location: pos.locationName || null,
      description: pos.description || null,
    };
  });

  const educations = profile.educations.map((edu) => ({
    school_name: edu.schoolName || null,
    school_linkedin_url: null,
    degree: edu.degreeName || null,
    field_of_study: edu.fieldOfStudy || null,
    start_year: parseYear(edu.startDate),
    end_year: parseYear(edu.endDate),
    description: edu.description || null,
  }));

  return {
    experiences,
    educations,
    skills: profile.skills,
  };
}
