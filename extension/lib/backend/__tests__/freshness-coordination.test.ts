// SPDX-License-Identifier: Apache-2.0
/**
 * Tests for the freshness check coordination logic used in background.ts.
 *
 * These tests verify the parallel freshness check pattern:
 * - URL_CHANGED starts checkFreshness() in parallel with Voyager fetch
 * - processVoyagerData() awaits the already-in-flight freshnessPromise
 * - Correct badge status is resolved for manual mode
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { checkFreshness, BackendUnreachable } from '../client';
import type { FreshnessResult } from '../client';
import type { CrawledProfileResponse } from '../types';
import { getConfigSync } from '../../config';

// Mock fetch globally
const mockFetch = vi.fn();

beforeEach(() => {
  mockFetch.mockReset();
  vi.stubGlobal('fetch', mockFetch);
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-04-04T00:00:00Z'));
});

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response;
}

function makeProfile(overrides: Partial<CrawledProfileResponse> = {}): CrawledProfileResponse {
  return {
    id: 'cp_001',
    linkedin_url: 'https://www.linkedin.com/in/johndoe',
    public_identifier: 'johndoe',
    first_name: 'John',
    last_name: 'Doe',
    full_name: 'John Doe',
    headline: null,
    about: null,
    location_city: null,
    location_state: null,
    location_country: null,
    location_country_code: null,
    location_raw: null,
    connections_count: null,
    follower_count: null,
    open_to_work: null,
    premium: null,
    current_company_name: null,
    current_position: null,
    company_id: null,
    seniority_level: null,
    function_area: null,
    source_app_user_id: null,
    data_source: 'extension',
    has_enriched_data: false,
    last_crawled_at: '2026-03-20T00:00:00Z',
    profile_image_url: null,
    raw_profile: null,
    created_at: '2026-03-01T00:00:00Z',
    updated_at: '2026-03-20T00:00:00Z',
    ...overrides,
  };
}

/**
 * Simulate the background.ts coordination pattern:
 * 1. URL_CHANGED: start freshnessPromise
 * 2. VOYAGER_DATA_READY: await freshnessPromise, resolve badge status
 */
function simulateCoordination(freshnessPromise: Promise<FreshnessResult>) {
  // This mirrors processVoyagerData()'s manual-mode branch
  return async () => {
    const freshness = await freshnessPromise;

    let offline = false;
    if (freshness && 'offline' in freshness && freshness.offline) {
      offline = true;
    }

    if (!freshness || !freshness.exists) {
      return { badgeStatus: 'not_saved' as const, offline };
    } else if (freshness.staleDays < getConfigSync().stalenessDays) {
      return {
        badgeStatus: 'up_to_date' as const,
        crawledProfileId: freshness.id,
        staleDays: freshness.staleDays,
        offline: false,
      };
    } else {
      return {
        badgeStatus: 'stale' as const,
        crawledProfileId: freshness.id,
        staleDays: freshness.staleDays,
        offline: false,
      };
    }
  };
}

describe('freshness coordination (manual mode)', () => {
  it('fresh profile → badge shows up_to_date', async () => {
    // Profile crawled 10 days ago (within getConfigSync().stalenessDays)
    const profile = makeProfile({ last_crawled_at: '2026-03-25T00:00:00Z' });
    mockFetch.mockResolvedValueOnce(jsonResponse({ crawled_profiles: [profile] }));

    // URL_CHANGED: start freshness check
    const freshnessPromise = checkFreshness('https://www.linkedin.com/in/johndoe');

    // VOYAGER_DATA_READY: await and resolve
    const resolve = simulateCoordination(freshnessPromise);
    const result = await resolve();

    expect(result.badgeStatus).toBe('up_to_date');
    expect(result).toMatchObject({ crawledProfileId: 'cp_001', staleDays: 10 });
  });

  it('stale profile → badge shows stale', async () => {
    // Profile crawled 45 days ago (beyond getConfigSync().stalenessDays)
    const profile = makeProfile({ last_crawled_at: '2026-02-18T00:00:00Z' });
    mockFetch.mockResolvedValueOnce(jsonResponse({ crawled_profiles: [profile] }));

    const freshnessPromise = checkFreshness('https://www.linkedin.com/in/johndoe');
    const resolve = simulateCoordination(freshnessPromise);
    const result = await resolve();

    expect(result.badgeStatus).toBe('stale');
    expect(result).toMatchObject({ crawledProfileId: 'cp_001', staleDays: 45 });
  });

  it('not found → badge shows not_saved', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ crawled_profiles: [] }));

    const freshnessPromise = checkFreshness('https://www.linkedin.com/in/newperson');
    const resolve = simulateCoordination(freshnessPromise);
    const result = await resolve();

    expect(result.badgeStatus).toBe('not_saved');
    expect(result.offline).toBe(false);
  });

  it('backend unreachable → offline flag set, badge shows not_saved', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('fetch failed'));

    // Mirrors handleUrlChanged's .catch() handler
    const freshnessPromise = checkFreshness('https://www.linkedin.com/in/johndoe').catch((err) => {
      if (err instanceof BackendUnreachable) return { exists: false, offline: true } as FreshnessResult;
      return { exists: false } as FreshnessResult;
    });

    const resolve = simulateCoordination(freshnessPromise);
    const result = await resolve();

    expect(result.badgeStatus).toBe('not_saved');
    expect(result.offline).toBe(true);
  });

  it('rapid navigation → second promise used, first discarded', async () => {
    // First navigation: slow response
    let resolveFirst!: (v: Response) => void;
    const firstFetch = new Promise<Response>((r) => { resolveFirst = r; });
    mockFetch.mockReturnValueOnce(firstFetch);

    // Start first freshness check (URL_CHANGED #1)
    const firstPromise = checkFreshness('https://www.linkedin.com/in/first').catch(
      () => ({ exists: false }) as FreshnessResult,
    );

    // Second navigation immediately (URL_CHANGED #2) — this replaces freshnessPromise
    const fastProfile = makeProfile({ id: 'cp_second', last_crawled_at: '2026-03-30T00:00:00Z' });
    mockFetch.mockResolvedValueOnce(jsonResponse({ crawled_profiles: [fastProfile] }));

    const secondPromise = checkFreshness('https://www.linkedin.com/in/second').catch(
      () => ({ exists: false }) as FreshnessResult,
    );

    // Only the second promise is used (simulating freshnessPromise = secondPromise)
    const resolve = simulateCoordination(secondPromise);
    const result = await resolve();

    expect(result.badgeStatus).toBe('up_to_date');
    expect(result).toMatchObject({ crawledProfileId: 'cp_second', staleDays: 5 });

    // Resolve first (late) — it's discarded, no effect
    resolveFirst(jsonResponse({ crawled_profiles: [makeProfile({ id: 'cp_first' })] }));
    await firstPromise; // just drain it
  });
});
