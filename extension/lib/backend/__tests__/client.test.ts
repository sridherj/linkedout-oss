// SPDX-License-Identifier: Apache-2.0
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { checkFreshness, createProfile, updateProfile, getRecentActivity, enrichProfile, BackendUnreachable, BackendError } from '../client';
import type { CrawledProfilePayload, CrawledProfileResponse, EnrichProfilePayload } from '../types';

// ── Mocks ──────────────────────────────────────────────────

const mockFetch = vi.fn();

beforeEach(() => {
  mockFetch.mockReset();
  vi.stubGlobal('fetch', mockFetch);
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-04-04T00:00:00Z'));
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
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

// ── checkFreshness ─────────────────────────────────────────

describe('checkFreshness', () => {
  it('calls GET /crawled-profiles?linkedin_url={normalized}&limit=1', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ crawled_profiles: [] }));

    await checkFreshness('https://www.linkedin.com/in/johndoe');

    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toContain('/crawled-profiles?');
    expect(url).toContain('linkedin_url=');
    expect(url).toContain('limit=1');
    expect(init?.headers?.['X-App-User-Id']).toBeDefined();
  });

  it('sends X-App-User-Id header', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ crawled_profiles: [] }));

    await checkFreshness('https://www.linkedin.com/in/johndoe');

    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers['X-App-User-Id']).toBe('usr_sys_001');
  });

  it('returns { exists: false } for invalid URL (no fetch)', async () => {
    const result = await checkFreshness('not-a-url');
    expect(result).toEqual({ exists: false });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('returns { exists: false } for empty result', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ crawled_profiles: [] }));

    const result = await checkFreshness('https://www.linkedin.com/in/johndoe');
    expect(result).toEqual({ exists: false });
  });

  it('returns correct staleDays for fresh profile (within 30 days)', async () => {
    // last_crawled_at = 15 days ago
    const profile = makeProfile({ last_crawled_at: '2026-03-20T00:00:00Z' });
    mockFetch.mockResolvedValueOnce(jsonResponse({ crawled_profiles: [profile] }));

    const result = await checkFreshness('https://www.linkedin.com/in/johndoe');
    expect(result).toMatchObject({ exists: true, staleDays: 15 });
  });

  it('returns correct staleDays for stale profile (> 30 days)', async () => {
    // last_crawled_at = 45 days ago
    const profile = makeProfile({ last_crawled_at: '2026-02-18T00:00:00Z' });
    mockFetch.mockResolvedValueOnce(jsonResponse({ crawled_profiles: [profile] }));

    const result = await checkFreshness('https://www.linkedin.com/in/johndoe');
    expect(result).toMatchObject({ exists: true, staleDays: 45 });
  });

  it('treats null last_crawled_at as STALENESS_DAYS+1', async () => {
    const profile = makeProfile({ last_crawled_at: null });
    mockFetch.mockResolvedValueOnce(jsonResponse({ crawled_profiles: [profile] }));

    const result = await checkFreshness('https://www.linkedin.com/in/johndoe');
    expect(result).toMatchObject({ exists: true, staleDays: 31 }); // STALENESS_DAYS (30) + 1
  });
});

// ── createProfile ──────────────────────────────────────────

describe('createProfile', () => {
  it('POSTs to /crawled-profiles with full payload', async () => {
    const payload: CrawledProfilePayload = {
      linkedin_url: 'https://www.linkedin.com/in/johndoe',
      data_source: 'extension',
      first_name: 'John',
      last_name: 'Doe',
      full_name: 'John Doe',
    };
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ crawled_profile: { id: 'cp_new', ...payload } }),
    );

    await createProfile(payload);

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/crawled-profiles$/);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toMatchObject(payload);
  });

  it('returns profile ID from response', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ crawled_profile: { id: 'cp_42' } }),
    );

    const id = await createProfile({ linkedin_url: 'x', data_source: 'extension' } as CrawledProfilePayload);
    expect(id).toBe('cp_42');
  });
});

// ── updateProfile ──────────────────────────────────────────

describe('updateProfile', () => {
  it('PATCHes to /crawled-profiles/{id}', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({}));

    await updateProfile('cp_001', { headline: 'Updated' });

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/crawled-profiles\/cp_001$/);
    expect(init.method).toBe('PATCH');
  });
});

// ── getRecentActivity ──────────────────────────────────────

describe('getRecentActivity', () => {
  it('calls with correct query params, default limit=20', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ crawled_profiles: [] }));

    await getRecentActivity();

    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('data_source=extension');
    expect(url).toContain('sort_by=created_at');
    expect(url).toContain('sort_order=desc');
    expect(url).toContain('limit=20');
  });

  it('custom limit passed through', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ crawled_profiles: [] }));

    await getRecentActivity(5);

    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('limit=5');
  });
});

// ── enrichProfile ─────────────────────────────────────────

describe('enrichProfile', () => {
  const payload: EnrichProfilePayload = {
    experiences: [
      {
        position: 'Senior Engineer',
        company_name: 'Acme Corp',
        company_linkedin_url: 'https://www.linkedin.com/company/acme',
        company_universal_name: 'acme',
        start_year: 2022,
        start_month: 9,
        is_current: true,
      },
    ],
    educations: [
      {
        school_name: 'MIT',
        degree: 'BS',
        field_of_study: 'CS',
        start_year: 2018,
        end_year: 2022,
      },
    ],
    skills: ['TypeScript', 'Python'],
  };

  it('POSTs to /crawled-profiles/{id}/enrich', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({}));

    await enrichProfile('cp_001', payload);

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/crawled-profiles\/cp_001\/enrich$/);
    expect(init.method).toBe('POST');
  });

  it('sends payload as JSON body', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({}));

    await enrichProfile('cp_001', payload);

    const [, init] = mockFetch.mock.calls[0];
    const body = JSON.parse(init.body);
    expect(body.experiences).toHaveLength(1);
    expect(body.experiences[0].position).toBe('Senior Engineer');
    expect(body.educations).toHaveLength(1);
    expect(body.skills).toEqual(['TypeScript', 'Python']);
  });

  it('includes X-App-User-Id header', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({}));

    await enrichProfile('cp_001', payload);

    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers['X-App-User-Id']).toBe('usr_sys_001');
  });
});

// ── Error handling ─────────────────────────────────────────

describe('error handling', () => {
  it('network error throws BackendUnreachable', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('fetch failed'));

    await expect(checkFreshness('https://www.linkedin.com/in/johndoe'))
      .rejects.toThrow(BackendUnreachable);
  });

  it('4xx/5xx throws BackendError with status and detail message', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      text: () => Promise.resolve(JSON.stringify({ detail: 'Validation failed' })),
    } as unknown as Response);

    try {
      await checkFreshness('https://www.linkedin.com/in/johndoe');
      expect.unreachable('should have thrown');
    } catch (err) {
      expect(err).toBeInstanceOf(BackendError);
      expect((err as BackendError).status).toBe(422);
      expect((err as BackendError).message).toBe('Validation failed');
    }
  });
});
