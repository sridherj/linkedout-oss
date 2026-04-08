// SPDX-License-Identifier: Apache-2.0
/** Request/response types matching backend CrawledProfile contracts. */

/** Matches CreateCrawledProfileRequestSchema from the backend. */
export interface CrawledProfilePayload {
  linkedin_url: string;
  public_identifier?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  full_name?: string | null;
  headline?: string | null;
  about?: string | null;
  location_city?: string | null;
  location_state?: string | null;
  location_country?: string | null;
  location_country_code?: string | null;
  location_raw?: string | null;
  connections_count?: number | null;
  follower_count?: number | null;
  open_to_work?: boolean | null;
  premium?: boolean | null;
  current_company_name?: string | null;
  current_position?: string | null;
  company_id?: string | null;
  seniority_level?: string | null;
  function_area?: string | null;
  source_app_user_id?: string | null;
  data_source: string;
  has_enriched_data?: boolean;
  last_crawled_at?: string | null;
  profile_image_url?: string | null;
  raw_profile?: unknown | null;
}

/** Matches CrawledProfileSchema from the backend response. */
export interface CrawledProfileResponse {
  id: string;
  linkedin_url: string;
  public_identifier: string | null;
  first_name: string | null;
  last_name: string | null;
  full_name: string | null;
  headline: string | null;
  about: string | null;
  location_city: string | null;
  location_state: string | null;
  location_country: string | null;
  location_country_code: string | null;
  location_raw: string | null;
  connections_count: number | null;
  follower_count: number | null;
  open_to_work: boolean | null;
  premium: boolean | null;
  current_company_name: string | null;
  current_position: string | null;
  company_id: string | null;
  seniority_level: string | null;
  function_area: string | null;
  source_app_user_id: string | null;
  data_source: string;
  has_enriched_data: boolean;
  last_crawled_at: string | null;
  profile_image_url: string | null;
  raw_profile: unknown | null;
  created_at: string;
  updated_at: string;
}

/** Backend error response shape. */
export interface BackendError {
  detail: string;
  status_code?: number;
}

/** Matches EnrichProfileRequestSchema from backend. */
export interface EnrichExperienceItem {
  position?: string | null;
  company_name?: string | null;
  company_linkedin_url?: string | null;
  company_universal_name?: string | null;
  employment_type?: string | null;
  start_year?: number | null;
  start_month?: number | null;
  end_year?: number | null;
  end_month?: number | null;
  is_current?: boolean | null;
  location?: string | null;
  description?: string | null;
}

export interface EnrichEducationItem {
  school_name?: string | null;
  school_linkedin_url?: string | null;
  degree?: string | null;
  field_of_study?: string | null;
  start_year?: number | null;
  end_year?: number | null;
  description?: string | null;
}

export interface EnrichProfilePayload {
  experiences: EnrichExperienceItem[];
  educations: EnrichEducationItem[];
  skills: string[];
}
