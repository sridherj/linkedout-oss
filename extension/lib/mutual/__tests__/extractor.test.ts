// SPDX-License-Identifier: Apache-2.0
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  extractMutualConnectionUrls,
  extractProfileUrlsFromResponse,
  extractPagingTotal,
} from '../extractor';

// Mock constants (only true constants remain)
vi.mock('../../constants', () => ({
  VOYAGER_SEARCH_DECORATION_ID: 'com.linkedin.voyager.dash.deco.search.SearchClusterCollection-186',
  MUTUAL_PAGE_SIZE: 10,
}));

// Mock config so inter-page sleep is instant
vi.mock('../../config', () => ({
  getConfigSync: () => ({
    minFetchDelayMs: 0,
    maxFetchDelayMs: 0,
    mutualMaxPages: 10,
    mutualFirstPageDelayBaseMs: 0,
    mutualFirstPageDelayRangeMs: 0,
  }),
}));

// ── Mocks ──────────────────────────────────────────────────

const mockFetch = vi.fn();

beforeEach(() => {
  mockFetch.mockReset();
  vi.stubGlobal('fetch', mockFetch);
  // Mock document.cookie for CSRF extraction
  Object.defineProperty(globalThis, 'document', {
    value: { cookie: 'JSESSIONID="ajax:1234567890"' },
    writable: true,
    configurable: true,
  });
  // Mock Math.random for deterministic delays
  vi.spyOn(Math, 'random').mockReturnValue(0);
  // Suppress console.log/warn from the extractor
  vi.spyOn(console, 'log').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

const ENTITY_URN = 'ACoAAACwHOYBb00';
const noop = () => {};

/** Build a Voyager API response with N profile entities. */
function voyagerResponse(slugs: string[], total?: number): object {
  return {
    included: slugs.map(slug => ({
      navigationUrl: `https://www.linkedin.com/in/${slug}?miniProfileUrn=urn`,
    })),
    data: {
      paging: { total: total ?? slugs.length },
    },
  };
}

function jsonResponse(body: object, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response;
}

// ── Tests ──────────────────────────────────────────────────

describe('extractMutualConnectionUrls', () => {
  it('extracts profile URLs from Voyager API response', async () => {
    const slugs = ['alice', 'bob', 'carol'];
    // Page 0: 3 results (< PAGE_SIZE=10 → stops)
    mockFetch.mockResolvedValueOnce(jsonResponse(voyagerResponse(slugs, 3)));

    const result = await extractMutualConnectionUrls(ENTITY_URN, noop);

    expect(result.urls).toEqual(
      expect.arrayContaining(slugs.map(s => `https://www.linkedin.com/in/${s}`)),
    );
    expect(result.urls).toHaveLength(3);
  });

  it('deduplicates URLs across pages', async () => {
    // Page 0: 10 results (full page → continues)
    const fullPage = Array.from({ length: 10 }, (_, i) => `user-${i}`);
    mockFetch.mockResolvedValueOnce(jsonResponse(voyagerResponse(fullPage, 13)));
    // Page 1: overlap + new, < 10 → stops
    mockFetch.mockResolvedValueOnce(
      jsonResponse(voyagerResponse(['user-0', 'user-1', 'user-new'], 13)),
    );

    const result = await extractMutualConnectionUrls(ENTITY_URN, noop);

    // 10 unique from page 0 + 1 new from page 1 = 11
    expect(result.urls).toHaveLength(11);
  });

  it('excludes specified slugs', async () => {
    const slugs = ['alice', 'me', 'target'];
    mockFetch.mockResolvedValueOnce(jsonResponse(voyagerResponse(slugs, 3)));

    const result = await extractMutualConnectionUrls(ENTITY_URN, noop, undefined, ['me', 'target']);

    expect(result.urls).toHaveLength(1);
    expect(result.urls[0]).toContain('alice');
  });

  it('stops on empty page (no results)', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse(voyagerResponse([], 0)));

    const result = await extractMutualConnectionUrls(ENTITY_URN, noop);

    expect(result.stopped).toBe(true);
    expect(result.stopReason).toBe('no_more_results');
    expect(result.pagesScraped).toBe(1);
  });

  it('stops on partial page (< 10 results)', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse(voyagerResponse(['a', 'b', 'c'], 3)));

    const result = await extractMutualConnectionUrls(ENTITY_URN, noop);

    expect(result.stopped).toBe(false); // partial page = natural end, not "stopped"
    expect(result.urls).toHaveLength(3);
  });

  it('stops at MAX_PAGES (10)', async () => {
    // Return exactly 10 slugs on every page to force continuation
    for (let page = 0; page < 10; page++) {
      const slugs = Array.from({ length: 10 }, (_, i) => `p${page}-user-${i}`);
      mockFetch.mockResolvedValueOnce(jsonResponse(voyagerResponse(slugs, 100)));
    }

    const result = await extractMutualConnectionUrls(ENTITY_URN, noop);

    expect(result.pagesScraped).toBe(10);
    expect(result.stopReason).toBe('max_pages');
  });

  it('stops on 429 rate limit', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({}, 429));

    const result = await extractMutualConnectionUrls(ENTITY_URN, noop);

    expect(result.stopped).toBe(true);
    expect(result.stopReason).toBe('challenge');
  });

  it('stops on non-2xx response', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({}, 500));

    const result = await extractMutualConnectionUrls(ENTITY_URN, noop);

    expect(result.stopped).toBe(true);
    expect(result.stopReason).toBe('challenge');
    expect(result.pagesScraped).toBe(0);
  });

  it('AbortSignal cancels mid-pagination', async () => {
    const controller = new AbortController();
    // Page 0: full results
    const fullPage = Array.from({ length: 10 }, (_, i) => `user-${i}`);
    mockFetch.mockResolvedValueOnce(jsonResponse(voyagerResponse(fullPage, 100)));
    // Page 1: abort during fetch
    mockFetch.mockImplementationOnce(() => {
      controller.abort();
      return Promise.reject(new DOMException('Aborted', 'AbortError'));
    });

    const result = await extractMutualConnectionUrls(ENTITY_URN, noop, controller.signal);

    expect(result.stopped).toBe(true);
    expect(result.stopReason).toBe('cancelled');
  });

  it('returns challenge when no CSRF token', async () => {
    // Remove CSRF from cookies
    Object.defineProperty(globalThis, 'document', {
      value: { cookie: '' },
      writable: true,
      configurable: true,
    });

    const result = await extractMutualConnectionUrls(ENTITY_URN, noop);

    expect(result.stopped).toBe(true);
    expect(result.stopReason).toBe('challenge');
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('reports progress callback per page', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse(voyagerResponse(['a', 'b'], 2)));

    const progress = vi.fn();
    await extractMutualConnectionUrls(ENTITY_URN, progress);

    expect(progress).toHaveBeenCalledWith(1, 1); // page 1, total pages = ceil(2/10) = 1
  });

  it('strips urn:li:fsd_profile: prefix from entityUrn', async () => {
    const fullUrn = 'urn:li:fsd_profile:ACoAAACwHOYBb00';
    mockFetch.mockResolvedValueOnce(jsonResponse(voyagerResponse(['alice'], 1)));

    await extractMutualConnectionUrls(fullUrn, noop);

    // The URL should contain the raw member ID, not the full URN
    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toContain('connectionOf:List(ACoAAACwHOYBb00)');
    expect(calledUrl).not.toContain('urn:li:fsd_profile:');
  });
});

// ── Pure function tests (no mocks needed) ─────────────────

describe('extractProfileUrlsFromResponse', () => {
  it('extracts slugs from navigationUrl fields', () => {
    const data = {
      included: [
        { navigationUrl: 'https://www.linkedin.com/in/alice-smith?miniProfileUrn=foo' },
        { navigationUrl: 'https://www.linkedin.com/in/bob-jones?ref=bar' },
      ],
    };
    expect(extractProfileUrlsFromResponse(data)).toEqual([
      'https://www.linkedin.com/in/alice-smith',
      'https://www.linkedin.com/in/bob-jones',
    ]);
  });

  it('lowercases slugs', () => {
    const data = {
      included: [{ navigationUrl: 'https://www.linkedin.com/in/Alice-SMITH/' }],
    };
    expect(extractProfileUrlsFromResponse(data)).toEqual([
      'https://www.linkedin.com/in/alice-smith',
    ]);
  });

  it('excludes slugs in the exclude set', () => {
    const data = {
      included: [
        { navigationUrl: 'https://www.linkedin.com/in/alice/' },
        { navigationUrl: 'https://www.linkedin.com/in/me/' },
        { navigationUrl: 'https://www.linkedin.com/in/target/' },
      ],
    };
    const exclude = new Set(['me', 'target']);
    expect(extractProfileUrlsFromResponse(data, exclude)).toEqual([
      'https://www.linkedin.com/in/alice',
    ]);
  });

  it('skips entities without navigationUrl', () => {
    const data = {
      included: [
        { entityUrn: 'urn:li:fsd_profile:ACoAAAA' },
        { '$type': 'something' },
        { navigationUrl: 'https://www.linkedin.com/in/valid/' },
      ],
    };
    expect(extractProfileUrlsFromResponse(data)).toEqual([
      'https://www.linkedin.com/in/valid',
    ]);
  });

  it('skips non-profile navigationUrls', () => {
    const data = {
      included: [
        { navigationUrl: 'https://www.linkedin.com/company/acme/' },
        { navigationUrl: 'https://www.linkedin.com/jobs/view/12345/' },
        { navigationUrl: 'https://www.linkedin.com/in/real-person/' },
      ],
    };
    expect(extractProfileUrlsFromResponse(data)).toEqual([
      'https://www.linkedin.com/in/real-person',
    ]);
  });

  it('returns empty for null/undefined/empty data', () => {
    expect(extractProfileUrlsFromResponse(null)).toEqual([]);
    expect(extractProfileUrlsFromResponse(undefined)).toEqual([]);
    expect(extractProfileUrlsFromResponse({})).toEqual([]);
    expect(extractProfileUrlsFromResponse({ included: [] })).toEqual([]);
  });

  it('handles slugs with numbers and hyphens', () => {
    const data = {
      included: [
        { navigationUrl: 'https://www.linkedin.com/in/john-doe-123456/' },
        { navigationUrl: 'https://www.linkedin.com/in/a-b-99/' },
      ],
    };
    expect(extractProfileUrlsFromResponse(data)).toEqual([
      'https://www.linkedin.com/in/john-doe-123456',
      'https://www.linkedin.com/in/a-b-99',
    ]);
  });
});

describe('extractPagingTotal', () => {
  it('extracts total from standard response', () => {
    expect(extractPagingTotal({ data: { paging: { total: 42 } } })).toBe(42);
  });

  it('returns undefined when paging is missing', () => {
    expect(extractPagingTotal({ data: {} })).toBeUndefined();
    expect(extractPagingTotal({})).toBeUndefined();
  });

  it('returns undefined for null/undefined', () => {
    expect(extractPagingTotal(null)).toBeUndefined();
    expect(extractPagingTotal(undefined)).toBeUndefined();
  });

  it('returns 0 when total is 0', () => {
    expect(extractPagingTotal({ data: { paging: { total: 0 } } })).toBe(0);
  });
});
