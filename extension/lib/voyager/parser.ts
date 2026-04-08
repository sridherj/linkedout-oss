// SPDX-License-Identifier: Apache-2.0
/** Raw Voyager JSON → typed VoyagerProfile. */

import type {
  VoyagerRawResponse,
  VoyagerProfile,
  VoyagerPosition,
  VoyagerEducation,
  VoyagerGeo,
  VoyagerCompany,
  VoyagerCertification,
  VoyagerLanguage,
  VoyagerProject,
  VoyagerVolunteer,
  VoyagerCourse,
  VoyagerHonor,
  VoyagerIncludedEntity,
} from './types';

const TYPE_PROFILE =
  'com.linkedin.voyager.dash.identity.profile.Profile';
const TYPE_POSITION =
  'com.linkedin.voyager.dash.identity.profile.Position';
const TYPE_EDUCATION =
  'com.linkedin.voyager.dash.identity.profile.Education';
const TYPE_SKILL =
  'com.linkedin.voyager.dash.identity.profile.Skill';
const TYPE_GEO =
  'com.linkedin.voyager.dash.common.Geo';
const TYPE_INDUSTRY =
  'com.linkedin.voyager.dash.common.Industry';
const TYPE_COMPANY =
  'com.linkedin.voyager.dash.organization.Company';
const TYPE_CERTIFICATION =
  'com.linkedin.voyager.dash.identity.profile.Certification';
const TYPE_LANGUAGE =
  'com.linkedin.voyager.dash.identity.profile.Language';
const TYPE_PROJECT =
  'com.linkedin.voyager.dash.identity.profile.Project';
const TYPE_VOLUNTEER =
  'com.linkedin.voyager.dash.identity.profile.VolunteerExperience';
const TYPE_COURSE =
  'com.linkedin.voyager.dash.identity.profile.Course';
const TYPE_HONOR =
  'com.linkedin.voyager.dash.identity.profile.Honor';

export function formatDate(dateObj: unknown): string | null {
  if (!dateObj || typeof dateObj !== 'object') return null;
  const d = dateObj as Record<string, unknown>;
  const year = d.year as number | undefined;
  if (!year) return null;
  const month = d.month as number | undefined;
  return month ? `${year}-${String(month).padStart(2, '0')}` : `${year}`;
}

function byType(
  included: VoyagerIncludedEntity[],
  type: string,
): VoyagerIncludedEntity[] {
  return included.filter((item) => item.$type === type);
}

function findByUrn(
  included: VoyagerIncludedEntity[],
  urn: string | undefined,
): VoyagerIncludedEntity | undefined {
  if (!urn) return undefined;
  return included.find((item) => item.entityUrn === urn);
}

function extractProfilePicture(profile: VoyagerIncludedEntity): string | null {
  try {
    const pic = profile.profilePicture as Record<string, any> | undefined;
    const vec = pic?.displayImageReference?.vectorImage;
    if (!vec?.artifacts?.length) return null;
    const rootUrl: string = vec.rootUrl;
    const largest = vec.artifacts[vec.artifacts.length - 1];
    return rootUrl + largest.fileIdentifyingUrlPathSegment;
  } catch {
    return null;
  }
}

function resolveGeo(
  profile: VoyagerIncludedEntity,
  included: VoyagerIncludedEntity[],
): VoyagerGeo | null {
  const geoLocation = profile.geoLocation as Record<string, any> | undefined;
  const location = profile.location as Record<string, any> | undefined;
  const geoUrn = geoLocation?.geoUrn as string | undefined ??
    geoLocation?.['*geo'] as string | undefined;

  const geoEntity = geoUrn ? findByUrn(included, geoUrn) : undefined;
  if (!geoEntity && !location) return null;

  const fullName = (geoEntity?.defaultLocalizedName as string) ?? null;
  const withoutCountry = (geoEntity?.defaultLocalizedNameWithoutCountryName as string) ?? null;
  const countryCode = (location?.countryCode as string) ?? null;

  // Parse city/state from "City, State" or "City, State, Country"
  let city: string | null = null;
  let state: string | null = null;
  let country: string | null = null;

  if (withoutCountry) {
    const parts = withoutCountry.split(',').map((s: string) => s.trim());
    city = parts[0] ?? null;
    state = parts[1] ?? null;
  } else if (fullName) {
    const parts = fullName.split(',').map((s: string) => s.trim());
    if (parts.length >= 3) {
      city = parts[0] ?? null;
      state = parts[1] ?? null;
      country = parts[2] ?? null;
    } else if (parts.length === 2) {
      city = parts[0] ?? null;
      country = parts[1] ?? null;
    } else {
      country = parts[0] ?? null;
    }
  }

  // Resolve country name from country Geo entity
  const countryUrn = geoEntity?.['*country'] as string | undefined ??
    geoEntity?.countryUrn as string | undefined;
  if (countryUrn && !country) {
    const countryEntity = findByUrn(included, countryUrn);
    country = (countryEntity?.defaultLocalizedName as string) ?? null;
  }

  return { city, state, country, countryCode, fullName };
}

function resolveIndustry(
  profile: VoyagerIncludedEntity,
  included: VoyagerIncludedEntity[],
): string | null {
  const industryUrn = profile.industryUrn as string | undefined ??
    profile['*industry'] as string | undefined;
  if (!industryUrn) return null;
  const industryEntity = findByUrn(included, industryUrn);
  return (industryEntity?.name as string) ?? null;
}

function parseCompanies(included: VoyagerIncludedEntity[]): VoyagerCompany[] {
  return byType(included, TYPE_COMPANY).map((c) => {
    let industry: string | null = null;
    const indObj = c.industry as Record<string, string> | undefined;
    if (indObj) {
      const indUrn = Object.values(indObj).find((v) => typeof v === 'string' && v.startsWith('urn:'));
      if (indUrn) {
        const indEntity = findByUrn(included, indUrn);
        industry = (indEntity?.name as string) ?? null;
      }
    }

    let employeeCountRange: { start: number; end?: number } | null = null;
    const ecr = c.employeeCountRange as Record<string, unknown> | undefined;
    if (ecr && typeof ecr.start === 'number') {
      employeeCountRange = { start: ecr.start as number };
      if (typeof ecr.end === 'number') {
        employeeCountRange.end = ecr.end as number;
      }
    }

    return {
      entityUrn: (c.entityUrn as string) ?? '',
      name: (c.name as string) ?? '',
      universalName: (c.universalName as string) ?? null,
      url: (c.url as string) ?? null,
      industry,
      employeeCountRange,
    };
  });
}

/**
 * Parse raw Voyager JSON into a typed VoyagerProfile.
 * @param raw - The raw Voyager API response envelope.
 * @returns Parsed profile, or null if the response is empty/errored.
 */
export function parseVoyagerProfile(
  raw: VoyagerRawResponse,
): VoyagerProfile | null {
  if (raw.error) return null;

  const included = raw.included ?? [];
  if (included.length === 0) return null;

  const profile = byType(included, TYPE_PROFILE)[0];
  if (!profile) return null;

  const positions: VoyagerPosition[] = byType(included, TYPE_POSITION).map(
    (pos) => ({
      companyName: (pos.companyName as string) ?? '',
      title: (pos.title as string) ?? '',
      startDate: formatDate((pos.dateRange as any)?.start),
      endDate: formatDate((pos.dateRange as any)?.end),
      locationName: (pos.geoLocationName as string) ?? (pos.locationName as string) ?? null,
      companyUrn: (pos.companyUrn as string) ?? null,
      description: (pos.description as string) ?? null,
    }),
  );

  const educations: VoyagerEducation[] = byType(included, TYPE_EDUCATION).map(
    (edu) => ({
      schoolName: (edu.schoolName as string) ?? '',
      degreeName: (edu.degreeName as string) ?? null,
      fieldOfStudy: (edu.fieldOfStudy as string) ?? null,
      startDate: formatDate((edu.dateRange as any)?.start),
      endDate: formatDate((edu.dateRange as any)?.end),
      grade: (edu.grade as string) ?? null,
      description: (edu.description as string) ?? null,
      activities: (edu.activities as string) ?? null,
    }),
  );

  const skills: string[] = byType(included, TYPE_SKILL)
    .map((s) => (s.name as string) ?? '')
    .filter(Boolean);

  const certifications: VoyagerCertification[] = byType(included, TYPE_CERTIFICATION).map(
    (cert) => ({
      name: (cert.name as string) ?? '',
      authority: (cert.authority as string) ?? null,
      startDate: formatDate((cert.dateRange as any)?.start ?? (cert.timePeriod as any)?.startDate),
      endDate: formatDate((cert.dateRange as any)?.end ?? (cert.timePeriod as any)?.endDate),
    }),
  );

  const languages: VoyagerLanguage[] = byType(included, TYPE_LANGUAGE).map(
    (lang) => ({
      name: (lang.name as string) ?? '',
      proficiency: (lang.proficiency as string) ?? null,
    }),
  );

  const projects: VoyagerProject[] = byType(included, TYPE_PROJECT).map(
    (proj) => ({
      title: (proj.title as string) ?? '',
      description: (proj.description as string) ?? null,
      startDate: formatDate((proj.dateRange as any)?.start ?? (proj.timePeriod as any)?.startDate),
      endDate: formatDate((proj.dateRange as any)?.end ?? (proj.timePeriod as any)?.endDate),
    }),
  );

  const volunteerExperiences: VoyagerVolunteer[] = byType(included, TYPE_VOLUNTEER).map(
    (vol) => ({
      role: (vol.role as string) ?? (vol.title as string) ?? '',
      companyName: (vol.companyName as string) ?? null,
      startDate: formatDate((vol.dateRange as any)?.start),
      endDate: formatDate((vol.dateRange as any)?.end),
      description: (vol.description as string) ?? null,
    }),
  );

  const courses: VoyagerCourse[] = byType(included, TYPE_COURSE).map(
    (c) => ({
      name: (c.name as string) ?? '',
      number: (c.number as string) ?? null,
    }),
  );

  const honors: VoyagerHonor[] = byType(included, TYPE_HONOR).map(
    (h) => ({
      title: (h.title as string) ?? '',
      issuer: (h.issuer as string) ?? null,
      issueDate: formatDate((h.issueDate as any)),
      description: (h.description as string) ?? null,
    }),
  );

  return {
    firstName: (profile.firstName as string) ?? '',
    lastName: (profile.lastName as string) ?? '',
    headline: (profile.headline as string) ?? '',
    locationName:
      (profile.locationName as string) ??
      (profile.geoLocationName as string) ??
      null,
    summary: (profile.summary as string) ?? '',
    entityUrn: (profile.entityUrn as string) ?? null,
    publicIdentifier: (profile.publicIdentifier as string) ?? null,
    connectionsCount: (profile.connectionsCount as number) ?? null,
    followerCount: (profile.followerCount as number) ?? null,
    openToWork: Boolean(
      (profile as any).openToWorkInfo ?? (profile as any).isOpenToWork,
    ),
    premium: Boolean((profile as any).premium),
    profilePicture: extractProfilePicture(profile),
    positions,
    educations,
    skills,
    geo: resolveGeo(profile, included),
    industry: resolveIndustry(profile, included),
    companies: parseCompanies(included),
    certifications,
    languages,
    projects,
    volunteerExperiences,
    courses,
    honors,
  };
}
