// SPDX-License-Identifier: Apache-2.0
import { describe, it, expect } from 'vitest';
import { parseVoyagerProfile, formatDate } from '../parser';
import {
  VOYAGER_FULL_PROFILE,
  VOYAGER_RICH_PROFILE,
  VOYAGER_ERROR_RESPONSE,
  VOYAGER_EMPTY_RESPONSE,
  VOYAGER_MINIMAL_PROFILE,
} from './fixtures';

describe('formatDate', () => {
  it('returns year-month when both present', () => {
    expect(formatDate({ year: 2022, month: 9 })).toBe('2022-09');
  });

  it('returns year only when no month', () => {
    expect(formatDate({ year: 2022 })).toBe('2022');
  });

  it('returns null for null/undefined', () => {
    expect(formatDate(null)).toBeNull();
    expect(formatDate(undefined)).toBeNull();
  });

  it('returns null when year is 0', () => {
    expect(formatDate({ year: 0 })).toBeNull();
  });
});

describe('parseVoyagerProfile', () => {
  describe('error and edge cases', () => {
    it('returns null for error responses', () => {
      expect(parseVoyagerProfile(VOYAGER_ERROR_RESPONSE)).toBeNull();
    });

    it('returns null for empty included array', () => {
      expect(parseVoyagerProfile(VOYAGER_EMPTY_RESPONSE)).toBeNull();
    });

    it('returns null when no Profile entity exists', () => {
      expect(parseVoyagerProfile({
        included: [{ $type: 'com.linkedin.voyager.dash.identity.profile.Skill', name: 'Python' }],
      })).toBeNull();
    });
  });

  describe('minimal profile', () => {
    it('parses core fields with defaults for missing data', () => {
      const result = parseVoyagerProfile(VOYAGER_MINIMAL_PROFILE)!;
      expect(result).not.toBeNull();
      expect(result.firstName).toBe('Jane');
      expect(result.lastName).toBe('Doe');
      expect(result.headline).toBe('Software Engineer');
      expect(result.publicIdentifier).toBe('jane-doe');
      expect(result.geo).toBeNull();
      expect(result.industry).toBeNull();
      expect(result.positions).toEqual([]);
      expect(result.educations).toEqual([]);
      expect(result.skills).toEqual([]);
      expect(result.companies).toEqual([]);
      expect(result.certifications).toEqual([]);
      expect(result.languages).toEqual([]);
      expect(result.projects).toEqual([]);
      expect(result.volunteerExperiences).toEqual([]);
      expect(result.courses).toEqual([]);
      expect(result.honors).toEqual([]);
    });
  });

  describe('full profile (positions, education, geo, industry, companies)', () => {
    const result = parseVoyagerProfile(VOYAGER_FULL_PROFILE)!;

    it('parses core identity fields', () => {
      expect(result.firstName).toBe('Yogesh');
      expect(result.lastName).toBe('Vaishnav');
      expect(result.headline).toBe('Senior HR Manager at Adani Group');
      expect(result.summary).toBe('HR professional with 9+ years of experience in HR operations.');
      expect(result.publicIdentifier).toBe('yogesh-vaishnav-9440b449');
      expect(result.entityUrn).toBe('urn:li:fsd_profile:ACoAAAooq0QBKqyFbRslB-MNeSZryh3kMEreKvg');
    });

    it('resolves structured geo from Geo entities', () => {
      expect(result.geo).toEqual({
        city: 'Ahmedabad',
        state: 'Gujarat',
        country: 'India',
        countryCode: 'in',
        fullName: 'Ahmedabad, Gujarat, India',
      });
    });

    it('resolves industry from Industry entity', () => {
      expect(result.industry).toBe('Civil Engineering');
    });

    it('parses profile picture from vectorImage artifacts', () => {
      expect(result.profilePicture).toBe(
        'https://media.licdn.com/dms/image/v2/C5103AQHJAlGHm_JugA/profile-800_800/photo.jpg',
      );
    });

    it('parses positions with companyUrn and locationName', () => {
      expect(result.positions).toHaveLength(2);

      const current = result.positions[0];
      expect(current.companyName).toBe('Adani Group');
      expect(current.title).toBe('Associate Manager Human Resources');
      expect(current.startDate).toBe('2022-09');
      expect(current.endDate).toBeNull();
      expect(current.locationName).toBe('Ahmedabad, Gujarat, India');
      expect(current.companyUrn).toBe('urn:li:fsd_company:45812');

      const past = result.positions[1];
      expect(past.companyName).toBe('PASONA India Private Limited');
      expect(past.endDate).toBe('2022-08');
      expect(past.description).toBe('Managed recruitment operations for IT and non-IT sectors.');
    });

    it('parses education with grade', () => {
      expect(result.educations).toHaveLength(2);

      const eng = result.educations[0];
      expect(eng.schoolName).toBe('Ganpat University');
      expect(eng.degreeName).toBe('Bachelor of Engineering - BE');
      expect(eng.fieldOfStudy).toBe('Information Technology');
      expect(eng.grade).toBe('7.2 CGPA');
      expect(eng.startDate).toBe('2010');
      expect(eng.endDate).toBe('2014');
    });

    it('parses skills', () => {
      expect(result.skills).toEqual(['Talent Acquisition', 'HR Operations', 'Employee Relations']);
    });

    it('parses company entities with industry resolution', () => {
      expect(result.companies).toHaveLength(2);

      const adani = result.companies.find((c) => c.name === 'Adani Group')!;
      expect(adani.universalName).toBe('adani-group');
      expect(adani.url).toBe('https://www.linkedin.com/company/adani-group/');
      expect(adani.industry).toBe('Utilities');
      expect(adani.employeeCountRange).toEqual({ start: 10001 });

      const pasona = result.companies.find((c) => c.name === 'PASONA India Private Limited')!;
      expect(pasona.industry).toBe('Staffing & Recruiting');
      expect(pasona.employeeCountRange).toEqual({ start: 51, end: 200 });
    });

    it('returns empty arrays for absent collections', () => {
      expect(result.certifications).toEqual([]);
      expect(result.languages).toEqual([]);
      expect(result.projects).toEqual([]);
      expect(result.volunteerExperiences).toEqual([]);
      expect(result.courses).toEqual([]);
      expect(result.honors).toEqual([]);
    });
  });

  describe('rich profile (certifications, languages, projects, volunteering)', () => {
    const result = parseVoyagerProfile(VOYAGER_RICH_PROFILE)!;

    it('resolves geo for French location', () => {
      expect(result.geo).toEqual({
        city: 'Colombes',
        state: 'Île-de-France',
        country: 'France',
        countryCode: 'fr',
        fullName: 'Colombes, Île-de-France, France',
      });
    });

    it('resolves industry', () => {
      expect(result.industry).toBe('Higher Education');
    });

    it('parses certifications', () => {
      expect(result.certifications).toHaveLength(2);
      expect(result.certifications[0]).toEqual({
        name: 'Google Data Analytics Professional Certificate',
        authority: 'Google',
        startDate: '2024-01',
        endDate: null,
      });
      expect(result.certifications[1]).toEqual({
        name: 'AWS Cloud Practitioner',
        authority: 'Amazon Web Services',
        startDate: '2023-06',
        endDate: '2026-06',
      });
    });

    it('parses languages with proficiency', () => {
      expect(result.languages).toEqual([
        { name: 'English', proficiency: 'FULL_PROFESSIONAL' },
        { name: 'French', proficiency: 'LIMITED_WORKING' },
      ]);
    });

    it('parses projects', () => {
      expect(result.projects).toHaveLength(1);
      expect(result.projects[0]).toEqual({
        title: 'Customer Churn Prediction Model',
        description: 'Built ML model to predict customer churn using Python and scikit-learn.',
        startDate: '2024-03',
        endDate: '2024-05',
      });
    });

    it('parses volunteer experiences', () => {
      expect(result.volunteerExperiences).toHaveLength(1);
      expect(result.volunteerExperiences[0]).toEqual({
        role: 'Teaching Assistant',
        companyName: 'Code.org',
        startDate: '2023-09',
        endDate: null,
        description: 'Helped students learn basic programming concepts.',
      });
    });

    it('parses courses', () => {
      expect(result.courses).toEqual([
        { name: 'Machine Learning Specialization', number: 'CS229' },
      ]);
    });

    it('parses honors', () => {
      expect(result.honors).toHaveLength(1);
      expect(result.honors[0]).toEqual({
        title: "Dean's List 2024",
        issuer: 'EMLV Business School',
        issueDate: '2024',
        description: 'Top 10% of graduating class.',
      });
    });

    it('parses skills', () => {
      expect(result.skills).toEqual(['Data Analysis', 'SQL']);
    });
  });
});
