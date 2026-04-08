// SPDX-License-Identifier: Apache-2.0
/** Typed message contracts for cross-context communication. */

// ── Side panel → SW (enrich from cached Voyager data) ──
export interface EnrichProfile {
  type: 'ENRICH_PROFILE';
}

// ── SW → bridge → MAIN (re-sense after challenge cleared) ──
export interface RetryFetch {
  type: 'RETRY_FETCH';
}

// ── MAIN → bridge → SW (carries raw Voyager JSON) ──
export interface VoyagerDataReady {
  type: 'VOYAGER_DATA_READY';
  profileId: string;
  raw: unknown;
}

// ── Profile display status (spec state machine) ──
export type ProfileBadgeStatus =
  | 'loading'
  | 'not_saved'
  | 'saved_today'
  | 'up_to_date'
  | 'stale'
  | 'rate_limited'
  | 'save_failed'
  | 'challenge_detected';

// ── Profile display data for side panel ──
export interface ProfileDisplayData {
  name: string;
  headline: string | null;
  avatarUrl: string | null;
  location: string | null;
  connectionsCount: number | null;
  openToWork: boolean;
  linkedinUrl: string;
  entityUrn: string | null;
}

// ── SW → side panel (status badge + profile summary) ──
export interface ProfileStatusUpdate {
  type: 'PROFILE_STATUS_UPDATE';
  status: 'idle' | 'fetching' | 'ready' | 'saving' | 'done' | 'error' | 'skipped';
  badgeStatus?: ProfileBadgeStatus;
  profileName?: string;
  profileHeadline?: string;
  linkedinUrl?: string;
  errorMessage?: string;
  crawledProfileId?: string;
  profileData?: ProfileDisplayData;
  staleDays?: number;
}

// ── SW → side panel (current rate limit counters) ──
export interface RateLimitUpdate {
  type: 'RATE_LIMIT_UPDATE';
  hourly: { used: number; limit: number };
  daily: { used: number; limit: number };
}

// ── MAIN → bridge → SW (SPA navigation detected) ──
export interface UrlChanged {
  type: 'URL_CHANGED';
  url: string;
}


// ── MAIN → bridge → SW (Voyager fetch error) ──
export interface VoyagerDataError {
  type: 'VOYAGER_DATA_ERROR';
  profileId: string;
  errorType: 'csrf' | 'rate_limit' | 'challenge' | 'unknown';
  message: string;
}

// ── Best Hop: side panel → SW ──
export interface FindBestHop {
  type: 'FIND_BEST_HOP';
  entityUrn: string;
  linkedinUrl: string;
  profileName: string;
}

// ── Best Hop: SW → bridge → MAIN (trigger mutual extraction) ──
export interface ExtractMutualConnections {
  type: 'EXTRACT_MUTUAL_CONNECTIONS';
  entityUrn: string;
}

// ── Best Hop: MAIN → bridge → SW (extraction results) ──
export interface MutualConnectionsReady {
  type: 'MUTUAL_CONNECTIONS_READY';
  urls: string[];
  pagesScraped: number;
  stopped: boolean;
  stopReason?: string;
}

// ── Best Hop: SW → side panel (extraction progress) ──
export interface MutualExtractionProgress {
  type: 'MUTUAL_EXTRACTION_PROGRESS';
  page: number;
  total?: number;
}

// ── Best Hop: SW → side panel (individual search result) ──
export interface BestHopResult {
  type: 'BEST_HOP_RESULT';
  rank: number;
  name: string;
  role: string | null;
  affinityScore: number | null;
  reasoning: string | null;
  linkedinUrl: string | null;
}

// ── Best Hop: SW → side panel (thinking/status update) ──
export interface BestHopThinking {
  type: 'BEST_HOP_THINKING';
  message: string;
}

// ── Best Hop: SW → side panel (search finished) ──
export interface BestHopComplete {
  type: 'BEST_HOP_COMPLETE';
  totalResults: number;
  matched: number;
  unmatched: number;
}

// ── Best Hop: side panel → SW (set extraction speed multiplier) ──
export interface SetExtractionSpeed {
  type: 'SET_EXTRACTION_SPEED';
  multiplier: 1 | 2 | 4 | 8;
}

// ── Best Hop: SW → side panel (speed changed, e.g. after 429 auto-downshift) ──
export interface ExtractionSpeedChanged {
  type: 'EXTRACTION_SPEED_CHANGED';
  multiplier: 1 | 2 | 4 | 8;
}

// ── Best Hop: side panel → SW (cancel in-flight search) ──
export interface CancelBestHop {
  type: 'CANCEL_BEST_HOP';
}

// ── Best Hop: SW → side panel (error during any phase) ──
export interface BestHopError {
  type: 'BEST_HOP_ERROR';
  phase: 'extraction' | 'search';
  message: string;
}

// ── SW → side panel (backend offline status) ──
export interface OfflineStatusUpdate {
  type: 'OFFLINE_STATUS_UPDATE';
  isOffline: boolean;
}

// ── SW → side panel (challenge active status) ──
export interface ChallengeStatusUpdate {
  type: 'CHALLENGE_STATUS_UPDATE';
  isActive: boolean;
  message?: string;
}

// ── Side panel → SW (retry after challenge cleared) ──
export interface RetryAfterChallenge {
  type: 'RETRY_AFTER_CHALLENGE';
}

// ── SW → side panel (new log entry appended) ──
export interface LogUpdated {
  type: 'LOG_UPDATED';
  entry: {
    timestamp: string;
    action: string;
    profileName?: string;
    profileHeadline?: string;
    linkedinUrl?: string;
    reason?: string;
  };
}

/** Discriminated union of all extension messages. */
export type ExtensionMessage =
  | EnrichProfile
  | RetryFetch
  | VoyagerDataReady
  | VoyagerDataError
  | ProfileStatusUpdate
  | RateLimitUpdate
  | UrlChanged
  | FindBestHop
  | ExtractMutualConnections
  | MutualConnectionsReady
  | MutualExtractionProgress
  | BestHopResult
  | BestHopThinking
  | BestHopComplete
  | SetExtractionSpeed
  | ExtractionSpeedChanged
  | CancelBestHop
  | BestHopError
  | OfflineStatusUpdate
  | ChallengeStatusUpdate
  | RetryAfterChallenge
  | LogUpdated;
