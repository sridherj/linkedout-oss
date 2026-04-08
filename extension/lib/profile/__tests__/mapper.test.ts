// SPDX-License-Identifier: Apache-2.0
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { parseVoyagerProfile } from '../../voyager/parser';
import { toCrawledProfilePayload, toEnrichPayload, parseYear, parseMonth } from '../mapper';
import { VOYAGER_FULL_PROFILE, VOYAGER_RICH_PROFILE, VOYAGER_MINIMAL_PROFILE } from '../../voyager/__tests__/fixtures';

// Freeze time so last_crawled_at is deterministic
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-04-04T16:00:00.000Z'));
});

describe('toCrawledProfilePayload', () => {
  it('maps full profile to backend payload with location fields', () => {
    const profile = parseVoyagerProfile(VOYAGER_FULL_PROFILE)!;
    const payload = toCrawledProfilePayload(profile, 'yogesh-vaishnav-9440b449');

    expect(payload.linkedin_url).toBe('https://www.linkedin.com/in/yogesh-vaishnav-9440b449');
    expect(payload.public_identifier).toBe('yogesh-vaishnav-9440b449');
    expect(payload.first_name).toBe('Yogesh');
    expect(payload.last_name).toBe('Vaishnav');
    expect(payload.full_name).toBe('Yogesh Vaishnav');
    expect(payload.headline).toBe('Senior HR Manager at Adani Group');
    expect(payload.about).toBe('HR professional with 9+ years of experience in HR operations.');

    // Location fields — resolved from Geo entities
    expect(payload.location_city).toBe('Ahmedabad');
    expect(payload.location_state).toBe('Gujarat');
    expect(payload.location_country).toBe('India');
    expect(payload.location_country_code).toBe('in');
    expect(payload.location_raw).toBe('Ahmedabad, Gujarat, India');

    // Current position — first position without endDate
    expect(payload.current_company_name).toBe('Adani Group');
    expect(payload.current_position).toBe('Associate Manager Human Resources');

    // Profile image — constructed from rootUrl + largest artifact
    expect(payload.profile_image_url).toBe(
      'https://media.licdn.com/dms/image/v2/C5103AQHJAlGHm_JugA/profile-800_800/photo.jpg',
    );

    // Metadata
    expect(payload.data_source).toBe('extension');
    expect(payload.source_app_user_id).toBe('usr_sys_001');
    expect(payload.last_crawled_at).toBe('2026-04-04T16:00:00.000Z');

    // raw_profile should be the full parsed VoyagerProfile JSON
    const raw = JSON.parse(payload.raw_profile as string);
    expect(raw.geo.city).toBe('Ahmedabad');
    expect(raw.industry).toBe('Civil Engineering');
    expect(raw.companies).toHaveLength(2);
    expect(raw.positions).toHaveLength(2);
    expect(raw.educations).toHaveLength(2);
    expect(raw.skills).toHaveLength(3);
  });

  it('maps rich profile with certifications/languages in raw_profile', () => {
    const profile = parseVoyagerProfile(VOYAGER_RICH_PROFILE)!;
    const payload = toCrawledProfilePayload(profile, 'akshay--padmanabhan');

    expect(payload.location_city).toBe('Colombes');
    expect(payload.location_state).toBe('Île-de-France');
    expect(payload.location_country).toBe('France');
    expect(payload.location_country_code).toBe('fr');

    const raw = JSON.parse(payload.raw_profile as string);
    expect(raw.certifications).toHaveLength(2);
    expect(raw.certifications[0].name).toBe('Google Data Analytics Professional Certificate');
    expect(raw.languages).toHaveLength(2);
    expect(raw.projects).toHaveLength(1);
    expect(raw.volunteerExperiences).toHaveLength(1);
    expect(raw.courses).toHaveLength(1);
    expect(raw.honors).toHaveLength(1);
  });

  it('handles minimal profile with null location fields', () => {
    const profile = parseVoyagerProfile(VOYAGER_MINIMAL_PROFILE)!;
    const payload = toCrawledProfilePayload(profile, 'jane-doe');

    expect(payload.linkedin_url).toBe('https://www.linkedin.com/in/jane-doe');
    expect(payload.first_name).toBe('Jane');
    expect(payload.last_name).toBe('Doe');
    expect(payload.location_city).toBeNull();
    expect(payload.location_state).toBeNull();
    expect(payload.location_country).toBeNull();
    expect(payload.location_country_code).toBeNull();
    expect(payload.location_raw).toBeNull();
    expect(payload.current_company_name).toBeNull();
    expect(payload.current_position).toBeNull();
    expect(payload.profile_image_url).toBeNull();
  });
});

// ── parseYear / parseMonth ────────────────────────────────

describe('parseYear', () => {
  it('"2022-09" → 2022', () => expect(parseYear('2022-09')).toBe(2022));
  it('"2022" → 2022', () => expect(parseYear('2022')).toBe(2022));
  it('null → null', () => expect(parseYear(null)).toBeNull());
  it('"" → null', () => expect(parseYear('')).toBeNull());
});

describe('parseMonth', () => {
  it('"2022-09" → 9', () => expect(parseMonth('2022-09')).toBe(9));
  it('"2022" → null (no month part)', () => expect(parseMonth('2022')).toBeNull());
  it('null → null', () => expect(parseMonth(null)).toBeNull());
  it('"2022-01" → 1', () => expect(parseMonth('2022-01')).toBe(1));
});

// ── toEnrichPayload ───────────────────────────────────────

describe('toEnrichPayload', () => {
  it('maps full profile positions to experiences with company resolution', () => {
    const profile = parseVoyagerProfile(VOYAGER_FULL_PROFILE)!;
    const payload = toEnrichPayload(profile);

    expect(payload.experiences.length).toBeGreaterThan(0);

    const first = payload.experiences[0];
    expect(first.position).toBeDefined();
    expect(first.company_name).toBeDefined();
    // Company URL/universalName resolved from companies array
    expect(first).toHaveProperty('company_linkedin_url');
    expect(first).toHaveProperty('company_universal_name');
  });

  it('sets is_current: true when position has no endDate', () => {
    const profile = parseVoyagerProfile(VOYAGER_FULL_PROFILE)!;
    const payload = toEnrichPayload(profile);

    const currentExp = payload.experiences.find((e) => e.is_current === true);
    expect(currentExp).toBeDefined();
    expect(currentExp!.end_year).toBeNull();
    expect(currentExp!.end_month).toBeNull();
  });

  it('parses start/end dates into year and month', () => {
    const profile = parseVoyagerProfile(VOYAGER_FULL_PROFILE)!;
    const payload = toEnrichPayload(profile);

    // At least one experience should have start_year parsed
    const withStart = payload.experiences.find((e) => e.start_year !== null);
    expect(withStart).toBeDefined();
    expect(typeof withStart!.start_year).toBe('number');
  });

  it('maps educations correctly', () => {
    const profile = parseVoyagerProfile(VOYAGER_FULL_PROFILE)!;
    const payload = toEnrichPayload(profile);

    expect(payload.educations.length).toBeGreaterThan(0);
    const first = payload.educations[0];
    expect(first.school_name).toBeDefined();
    expect(first).toHaveProperty('degree');
    expect(first).toHaveProperty('field_of_study');
    expect(first).toHaveProperty('start_year');
    expect(first).toHaveProperty('end_year');
  });

  it('passes skills through as string array', () => {
    const profile = parseVoyagerProfile(VOYAGER_FULL_PROFILE)!;
    const payload = toEnrichPayload(profile);

    expect(Array.isArray(payload.skills)).toBe(true);
    expect(payload.skills.length).toBeGreaterThan(0);
    payload.skills.forEach((s) => expect(typeof s).toBe('string'));
  });

  it('handles minimal profile with empty arrays', () => {
    const profile = parseVoyagerProfile(VOYAGER_MINIMAL_PROFILE)!;
    const payload = toEnrichPayload(profile);

    expect(payload.experiences).toEqual([]);
    expect(payload.educations).toEqual([]);
    expect(payload.skills).toEqual([]);
  });
});
