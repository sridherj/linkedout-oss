// SPDX-License-Identifier: Apache-2.0
/**
 * Backend API client for the service worker.
 * Communicates with the LinkedOut backend for freshness checks,
 * profile creation, and profile updates.
 */

import { getConfigSync } from '../config';
import { devLog } from '../dev-log';
import { appendLog } from '../log';
import { normalizeLinkedinUrl } from '../profile/url';
import type { CrawledProfilePayload, CrawledProfileResponse, EnrichProfilePayload } from './types';

// ── Error types ──────────────────────────────────────────────

export class BackendUnreachable extends Error {
  constructor(cause?: unknown) {
    super('Backend is unreachable');
    this.name = 'BackendUnreachable';
    this.cause = cause;
  }
}

export class BackendError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'BackendError';
    this.status = status;
  }
}

// ── Result types ─────────────────────────────────────────────

export type FreshnessResult =
  | { exists: false; offline?: boolean }
  | { exists: true; id: string; staleDays: number; profile: CrawledProfileResponse };

// ── Internal helpers ─────────────────────────────────────────

function getHeaders(): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'X-App-User-Id': getConfigSync().userId,
  };
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const method = init?.method ?? 'GET';
  const startMs = performance.now();
  let res: Response;
  try {
    res = await fetch(url, { ...init, headers: { ...getHeaders(), ...init?.headers } });
  } catch (err) {
    const durationMs = Math.round(performance.now() - startMs);
    devLog('error', 'backend-client', `${method} ${url} failed (network)`, { durationMs, error: String(err) });
    appendLog({
      timestamp: new Date().toISOString(),
      action: 'error',
      reason: `Backend unreachable: ${method} ${url} (${durationMs}ms)`,
    });
    throw new BackendUnreachable(err);
  }

  const durationMs = Math.round(performance.now() - startMs);

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    let message = body;
    try {
      const json = JSON.parse(body);
      message = json.detail ?? body;
    } catch {
      // use raw body
    }
    devLog('error', 'backend-client', `${method} ${url} → ${res.status}`, { durationMs, error: message });
    appendLog({
      timestamp: new Date().toISOString(),
      action: 'error',
      reason: `Backend error: ${method} ${url} → ${res.status} (${durationMs}ms)`,
    });
    throw new BackendError(res.status, message);
  }

  devLog('info', 'backend-client', `${method} ${url} → ${res.status}`, { durationMs });
  return res.json() as Promise<T>;
}

// ── Public API ───────────────────────────────────────────────

interface ListResponse {
  crawled_profiles: CrawledProfileResponse[];
}

interface CreateResponse {
  crawled_profile: CrawledProfileResponse;
}

/**
 * Check whether a profile exists in the backend and how stale it is.
 */
export async function checkFreshness(linkedinUrl: string): Promise<FreshnessResult> {
  const normalized = normalizeLinkedinUrl(linkedinUrl);
  if (!normalized) return { exists: false };

  const params = new URLSearchParams({
    linkedin_url: normalized,
    limit: '1',
  });

  const { crawled_profiles } = await request<ListResponse>(
    `${getConfigSync().backendUrl}/crawled-profiles?${params}`,
  );

  if (!crawled_profiles || crawled_profiles.length === 0) return { exists: false };

  const profile = crawled_profiles[0];
  const staleDays = profile.last_crawled_at
    ? Math.floor(
        (Date.now() - new Date(profile.last_crawled_at).getTime()) / (1000 * 60 * 60 * 24),
      )
    : getConfigSync().stalenessDays + 1; // treat missing last_crawled_at as stale

  return { exists: true, id: profile.id, staleDays, profile };
}

/**
 * Create a new profile in the backend. Returns the new profile ID.
 */
export async function createProfile(payload: CrawledProfilePayload): Promise<string> {
  const { crawled_profile } = await request<CreateResponse>(
    `${getConfigSync().backendUrl}/crawled-profiles`,
    { method: 'POST', body: JSON.stringify(payload) },
  );
  return crawled_profile.id;
}

/**
 * Update an existing profile in the backend.
 */
export async function updateProfile(
  id: string,
  payload: Partial<CrawledProfilePayload>,
): Promise<void> {
  await request<unknown>(
    `${getConfigSync().backendUrl}/crawled-profiles/${id}`,
    { method: 'PATCH', body: JSON.stringify(payload) },
  );
}

/**
 * Send structured experience/education/skill data for a crawled profile.
 */
export async function enrichProfile(
  crawledProfileId: string,
  payload: EnrichProfilePayload,
): Promise<void> {
  await request<unknown>(
    `${getConfigSync().backendUrl}/crawled-profiles/${crawledProfileId}/enrich`,
    { method: 'POST', body: JSON.stringify(payload) },
  );
}

/**
 * Fetch recent extension-created profiles for the activity list.
 */
export async function getRecentActivity(limit?: number): Promise<CrawledProfileResponse[]> {
  const effectiveLimit = limit ?? getConfigSync().recentActivityLimit;
  const params = new URLSearchParams({
    data_source: 'extension',
    sort_by: 'created_at',
    sort_order: 'desc',
    limit: String(effectiveLimit),
  });

  const { crawled_profiles } = await request<ListResponse>(
    `${getConfigSync().backendUrl}/crawled-profiles?${params}`,
  );
  return crawled_profiles;
}
