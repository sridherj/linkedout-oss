// SPDX-License-Identifier: Apache-2.0
/**
 * Test fixtures built from a real Voyager decoration-93 response.
 * Stripped to essential fields; structure matches live LinkedIn data.
 */
import type { VoyagerRawResponse } from '../types';

/** Full profile with positions, education, skills, geo, industry, companies. */
export const VOYAGER_FULL_PROFILE: VoyagerRawResponse = {
  data: {},
  included: [
    // ── Profile entity ──
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Profile',
      entityUrn: 'urn:li:fsd_profile:ACoAAAooq0QBKqyFbRslB-MNeSZryh3kMEreKvg',
      firstName: 'Yogesh',
      lastName: 'Vaishnav',
      headline: 'Senior HR Manager at Adani Group',
      summary: 'HR professional with 9+ years of experience in HR operations.',
      publicIdentifier: 'yogesh-vaishnav-9440b449',
      locationName: null,
      geoLocationName: null,
      premium: false,
      influencer: false,
      creator: false,
      memorialized: false,
      industryUrn: 'urn:li:fsd_industry:51',
      '*industry': 'urn:li:fsd_industry:51',
      geoLocation: {
        '*geo': 'urn:li:fsd_geo:103758613',
        geoUrn: 'urn:li:fsd_geo:103758613',
        $type: 'com.linkedin.voyager.dash.identity.profile.ProfileGeoLocation',
      },
      location: {
        countryCode: 'in',
        $type: 'com.linkedin.voyager.dash.identity.profile.ProfileLocation',
      },
      profilePicture: {
        displayImageReference: {
          vectorImage: {
            rootUrl: 'https://media.licdn.com/dms/image/v2/C5103AQHJAlGHm_JugA/',
            artifacts: [
              { width: 100, height: 100, fileIdentifyingUrlPathSegment: 'profile-100_100/photo.jpg' },
              { width: 200, height: 200, fileIdentifyingUrlPathSegment: 'profile-200_200/photo.jpg' },
              { width: 400, height: 400, fileIdentifyingUrlPathSegment: 'profile-400_400/photo.jpg' },
              { width: 800, height: 800, fileIdentifyingUrlPathSegment: 'profile-800_800/photo.jpg' },
            ],
          },
        },
      },
    },
    // ── Geo entities ──
    {
      $type: 'com.linkedin.voyager.dash.common.Geo',
      entityUrn: 'urn:li:fsd_geo:103758613',
      defaultLocalizedName: 'Ahmedabad, Gujarat, India',
      defaultLocalizedNameWithoutCountryName: 'Ahmedabad, Gujarat',
      '*country': 'urn:li:fsd_geo:102713980',
      countryUrn: 'urn:li:fsd_geo:102713980',
    },
    {
      $type: 'com.linkedin.voyager.dash.common.Geo',
      entityUrn: 'urn:li:fsd_geo:102713980',
      defaultLocalizedName: 'India',
    },
    // ── Industry entities ──
    {
      $type: 'com.linkedin.voyager.dash.common.Industry',
      entityUrn: 'urn:li:fsd_industry:51',
      name: 'Civil Engineering',
    },
    {
      $type: 'com.linkedin.voyager.dash.common.Industry',
      entityUrn: 'urn:li:fsd_industry:59',
      name: 'Utilities',
    },
    {
      $type: 'com.linkedin.voyager.dash.common.Industry',
      entityUrn: 'urn:li:fsd_industry:104',
      name: 'Staffing & Recruiting',
    },
    // ── Company entities ──
    {
      $type: 'com.linkedin.voyager.dash.organization.Company',
      entityUrn: 'urn:li:fsd_company:45812',
      name: 'Adani Group',
      universalName: 'adani-group',
      url: 'https://www.linkedin.com/company/adani-group/',
      industry: { '*urn:li:fsd_industry:59': 'urn:li:fsd_industry:59' },
      employeeCountRange: { start: 10001, $type: 'com.linkedin.common.IntegerRange' },
    },
    {
      $type: 'com.linkedin.voyager.dash.organization.Company',
      entityUrn: 'urn:li:fsd_company:3839882',
      name: 'PASONA India Private Limited',
      universalName: 'team-pasona-india-co-ltd-',
      url: 'https://www.linkedin.com/company/team-pasona-india-co-ltd-/',
      industry: { '*urn:li:fsd_industry:104': 'urn:li:fsd_industry:104' },
      employeeCountRange: { start: 51, end: 200, $type: 'com.linkedin.common.IntegerRange' },
    },
    // ── Position entities ──
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Position',
      entityUrn: 'urn:li:fsd_profilePosition:(ACoAAAooq0QBKqyFbRslB,current)',
      companyName: 'Adani Group',
      title: 'Associate Manager Human Resources',
      companyUrn: 'urn:li:fsd_company:45812',
      locationName: 'Ahmedabad, Gujarat, India',
      geoLocationName: 'Ahmedabad, Gujarat, India',
      dateRange: {
        start: { month: 9, year: 2022, $type: 'com.linkedin.common.Date' },
        $type: 'com.linkedin.common.DateRange',
      },
    },
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Position',
      entityUrn: 'urn:li:fsd_profilePosition:(ACoAAAooq0QBKqyFbRslB,past1)',
      companyName: 'PASONA India Private Limited',
      title: 'Deputy Manager',
      companyUrn: 'urn:li:fsd_company:3839882',
      locationName: 'Ahmedabad Area, India',
      geoLocationName: 'Ahmedabad Area, India',
      description: 'Managed recruitment operations for IT and non-IT sectors.',
      dateRange: {
        start: { month: 7, year: 2018, $type: 'com.linkedin.common.Date' },
        end: { month: 8, year: 2022, $type: 'com.linkedin.common.Date' },
        $type: 'com.linkedin.common.DateRange',
      },
    },
    // ── Education entities ──
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Education',
      entityUrn: 'urn:li:fsd_profileEducation:(ACoAAAooq0QBKqyFbRslB,edu1)',
      schoolName: 'Ganpat University',
      degreeName: 'Bachelor of Engineering - BE',
      fieldOfStudy: 'Information Technology',
      grade: '7.2 CGPA',
      description: null,
      activities: null,
      dateRange: {
        start: { year: 2010, $type: 'com.linkedin.common.Date' },
        end: { year: 2014, $type: 'com.linkedin.common.Date' },
        $type: 'com.linkedin.common.DateRange',
      },
    },
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Education',
      entityUrn: 'urn:li:fsd_profileEducation:(ACoAAAooq0QBKqyFbRslB,edu2)',
      schoolName: 'Ahmedabad',
      degreeName: "Bachelor's Degree",
      fieldOfStudy: 'Commerce',
      grade: 'Pass',
      description: null,
      activities: null,
      dateRange: {
        start: { year: 2005, $type: 'com.linkedin.common.Date' },
        end: { year: 2010, $type: 'com.linkedin.common.Date' },
        $type: 'com.linkedin.common.DateRange',
      },
    },
    // ── Skill entities ──
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Skill',
      entityUrn: 'urn:li:fsd_skill:1',
      name: 'Talent Acquisition',
    },
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Skill',
      entityUrn: 'urn:li:fsd_skill:2',
      name: 'HR Operations',
    },
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Skill',
      entityUrn: 'urn:li:fsd_skill:3',
      name: 'Employee Relations',
    },
  ],
};

/** Profile with certifications, languages, projects, volunteering. */
export const VOYAGER_RICH_PROFILE: VoyagerRawResponse = {
  data: {},
  included: [
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Profile',
      entityUrn: 'urn:li:fsd_profile:rich123',
      firstName: 'Akshay',
      lastName: 'Padmanabhan',
      headline: 'MSc International Business | Data Analysis',
      summary: 'Pursuing MSc in International Business at EMLV.',
      publicIdentifier: 'akshay--padmanabhan',
      locationName: 'Colombes, Île-de-France, France',
      premium: false,
      industryUrn: 'urn:li:fsd_industry:4',
      geoLocation: {
        '*geo': 'urn:li:fsd_geo:999',
        geoUrn: 'urn:li:fsd_geo:999',
        $type: 'com.linkedin.voyager.dash.identity.profile.ProfileGeoLocation',
      },
      location: {
        countryCode: 'fr',
        $type: 'com.linkedin.voyager.dash.identity.profile.ProfileLocation',
      },
    },
    {
      $type: 'com.linkedin.voyager.dash.common.Geo',
      entityUrn: 'urn:li:fsd_geo:999',
      defaultLocalizedName: 'Colombes, Île-de-France, France',
      defaultLocalizedNameWithoutCountryName: 'Colombes, Île-de-France',
      '*country': 'urn:li:fsd_geo:998',
    },
    {
      $type: 'com.linkedin.voyager.dash.common.Geo',
      entityUrn: 'urn:li:fsd_geo:998',
      defaultLocalizedName: 'France',
    },
    {
      $type: 'com.linkedin.voyager.dash.common.Industry',
      entityUrn: 'urn:li:fsd_industry:4',
      name: 'Higher Education',
    },
    // ── Certifications ──
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Certification',
      entityUrn: 'urn:li:fsd_cert:1',
      name: 'Google Data Analytics Professional Certificate',
      authority: 'Google',
      dateRange: {
        start: { month: 1, year: 2024, $type: 'com.linkedin.common.Date' },
        $type: 'com.linkedin.common.DateRange',
      },
    },
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Certification',
      entityUrn: 'urn:li:fsd_cert:2',
      name: 'AWS Cloud Practitioner',
      authority: 'Amazon Web Services',
      dateRange: {
        start: { month: 6, year: 2023, $type: 'com.linkedin.common.Date' },
        end: { month: 6, year: 2026, $type: 'com.linkedin.common.Date' },
        $type: 'com.linkedin.common.DateRange',
      },
    },
    // ── Languages ──
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Language',
      entityUrn: 'urn:li:fsd_lang:1',
      name: 'English',
      proficiency: 'FULL_PROFESSIONAL',
    },
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Language',
      entityUrn: 'urn:li:fsd_lang:2',
      name: 'French',
      proficiency: 'LIMITED_WORKING',
    },
    // ── Projects ──
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Project',
      entityUrn: 'urn:li:fsd_proj:1',
      title: 'Customer Churn Prediction Model',
      description: 'Built ML model to predict customer churn using Python and scikit-learn.',
      dateRange: {
        start: { month: 3, year: 2024, $type: 'com.linkedin.common.Date' },
        end: { month: 5, year: 2024, $type: 'com.linkedin.common.Date' },
        $type: 'com.linkedin.common.DateRange',
      },
    },
    // ── Volunteer Experiences ──
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.VolunteerExperience',
      entityUrn: 'urn:li:fsd_vol:1',
      role: 'Teaching Assistant',
      companyName: 'Code.org',
      description: 'Helped students learn basic programming concepts.',
      dateRange: {
        start: { month: 9, year: 2023, $type: 'com.linkedin.common.Date' },
        $type: 'com.linkedin.common.DateRange',
      },
    },
    // ── Courses ──
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Course',
      entityUrn: 'urn:li:fsd_course:1',
      name: 'Machine Learning Specialization',
      number: 'CS229',
    },
    // ── Honors ──
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Honor',
      entityUrn: 'urn:li:fsd_honor:1',
      title: "Dean's List 2024",
      issuer: 'EMLV Business School',
      issueDate: { year: 2024, $type: 'com.linkedin.common.Date' },
      description: 'Top 10% of graduating class.',
    },
    // ── Skills ──
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Skill',
      entityUrn: 'urn:li:fsd_skill:10',
      name: 'Data Analysis',
    },
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Skill',
      entityUrn: 'urn:li:fsd_skill:11',
      name: 'SQL',
    },
  ],
};

/** Minimal response — error case. */
export const VOYAGER_ERROR_RESPONSE: VoyagerRawResponse = {
  error: { status: 403, message: 'Forbidden' },
};

/** Empty included array. */
export const VOYAGER_EMPTY_RESPONSE: VoyagerRawResponse = {
  data: {},
  included: [],
};

/** Profile with no geo, no industry, minimal data. */
export const VOYAGER_MINIMAL_PROFILE: VoyagerRawResponse = {
  data: {},
  included: [
    {
      $type: 'com.linkedin.voyager.dash.identity.profile.Profile',
      entityUrn: 'urn:li:fsd_profile:minimal',
      firstName: 'Jane',
      lastName: 'Doe',
      headline: 'Software Engineer',
      publicIdentifier: 'jane-doe',
    },
  ],
};
