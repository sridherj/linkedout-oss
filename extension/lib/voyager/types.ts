// SPDX-License-Identifier: Apache-2.0
/** TypeScript types for the Voyager API response. */

/** The raw JSON envelope returned by LinkedIn's Voyager API. */
export interface VoyagerRawResponse {
  data?: Record<string, unknown>;
  included?: VoyagerIncludedEntity[];
  error?: unknown;
  [key: string]: unknown;
}

/** A single entity in the `included[]` array. */
export interface VoyagerIncludedEntity {
  $type: string;
  entityUrn?: string;
  [key: string]: unknown;
}

/** Parsed intermediate profile from Voyager data. */
export interface VoyagerProfile {
  firstName: string;
  lastName: string;
  headline: string;
  locationName: string | null;
  summary: string | null;
  entityUrn: string | null;
  publicIdentifier: string | null;
  connectionsCount: number | null;
  followerCount: number | null;
  openToWork: boolean;
  premium: boolean;
  profilePicture: string | null;
  positions: VoyagerPosition[];
  educations: VoyagerEducation[];
  skills: string[];
  /** Structured geo from Geo entity resolution. */
  geo: VoyagerGeo | null;
  /** Profile industry from Industry entity resolution. */
  industry: string | null;
  /** Company details for each position's companyUrn. */
  companies: VoyagerCompany[];
  /** Certifications (empty array if none). */
  certifications: VoyagerCertification[];
  /** Languages (empty array if none). */
  languages: VoyagerLanguage[];
  /** Projects (empty array if none). */
  projects: VoyagerProject[];
  /** Volunteer experiences (empty array if none). */
  volunteerExperiences: VoyagerVolunteer[];
  /** Courses (empty array if none). */
  courses: VoyagerCourse[];
  /** Honors/awards (empty array if none). */
  honors: VoyagerHonor[];
}

export interface VoyagerPosition {
  companyName: string;
  title: string;
  startDate: string | null;
  endDate: string | null;
  locationName: string | null;
  companyUrn: string | null;
  description: string | null;
}

export interface VoyagerEducation {
  schoolName: string;
  degreeName: string | null;
  fieldOfStudy: string | null;
  startDate: string | null;
  endDate: string | null;
  grade: string | null;
  description: string | null;
  activities: string | null;
}

export interface VoyagerGeo {
  city: string | null;
  state: string | null;
  country: string | null;
  countryCode: string | null;
  fullName: string | null;
}

export interface VoyagerCompany {
  entityUrn: string;
  name: string;
  universalName: string | null;
  url: string | null;
  industry: string | null;
  employeeCountRange: { start: number; end?: number } | null;
}

export interface VoyagerCertification {
  name: string;
  authority: string | null;
  startDate: string | null;
  endDate: string | null;
}

export interface VoyagerLanguage {
  name: string;
  proficiency: string | null;
}

export interface VoyagerProject {
  title: string;
  description: string | null;
  startDate: string | null;
  endDate: string | null;
}

export interface VoyagerVolunteer {
  role: string;
  companyName: string | null;
  startDate: string | null;
  endDate: string | null;
  description: string | null;
}

export interface VoyagerCourse {
  name: string;
  number: string | null;
}

export interface VoyagerHonor {
  title: string;
  issuer: string | null;
  issueDate: string | null;
  description: string | null;
}
