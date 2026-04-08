// SPDX-License-Identifier: Apache-2.0
/**
 * Mutual connection extractor — uses Voyager search API (runs in MAIN world).
 *
 * LinkedIn's search pages are client-rendered (RSC), so HTML scraping returns
 * an empty shell. Instead we call the same Voyager search/dash/clusters endpoint
 * that LinkedIn's own frontend uses to render search results.
 */

import { VOYAGER_SEARCH_DECORATION_ID, MUTUAL_PAGE_SIZE } from '../constants';
import { getConfigSync } from '../config';
import { normalizeLinkedinUrl } from '../profile/url';

export interface MutualExtractionResult {
  urls: string[];
  pagesScraped: number;
  stopped: boolean;
  stopReason?: 'cancelled' | 'challenge' | 'no_more_results' | 'max_pages';
}

function randomDelay(): number {
  const config = getConfigSync();
  return config.minFetchDelayMs + Math.random() * (config.maxFetchDelayMs - config.minFetchDelayMs);
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'));
      return;
    }
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(timer);
      reject(new DOMException('Aborted', 'AbortError'));
    }, { once: true });
  });
}

function extractCsrf(): string | null {
  const match = document.cookie.match(/JSESSIONID="?([^";]+)"?/);
  return match ? match[1] : null;
}

/**
 * Extract profile URLs from a Voyager search/dash/clusters response.
 * Pure function — no side effects, fully testable.
 */
export function extractProfileUrlsFromResponse(
  data: any,
  excludeSlugs?: Set<string>,
): string[] {
  const included: any[] = data?.included ?? [];
  const urls: string[] = [];

  for (const entity of included) {
    const navUrl: string | undefined = entity?.navigationUrl;
    if (!navUrl) continue;
    const match = navUrl.match(/\/in\/([a-zA-Z0-9\-]+)/);
    if (!match) continue;
    const slug = match[1].toLowerCase();
    if (excludeSlugs?.has(slug)) continue;
    const normalized = normalizeLinkedinUrl(`https://www.linkedin.com/in/${slug}`);
    if (normalized) urls.push(normalized);
  }

  return urls;
}

/**
 * Extract paging metadata from a Voyager search response.
 * Pure function — fully testable.
 */
export function extractPagingTotal(data: any): number | undefined {
  return data?.data?.paging?.total ?? undefined;
}

/**
 * Fetch mutual connections via LinkedIn's Voyager search API.
 *
 * @param entityUrn - The target profile's entityUrn (e.g. "ACoAAACwHOYBb00...")
 * @param onProgress - Called after each page: (currentPage, totalEstimate)
 * @param signal - Optional AbortSignal for cancellation
 * @param excludeSlugs - Profile slugs to exclude from results (e.g. current user, target)
 */
export async function extractMutualConnectionUrls(
  entityUrn: string,
  onProgress: (page: number, total?: number) => void,
  signal?: AbortSignal,
  excludeSlugs?: string[],
  getSpeed?: () => number,
  onSpeedDownshift?: () => void,
): Promise<MutualExtractionResult> {
  const excludeSet = new Set((excludeSlugs ?? []).map(s => s.toLowerCase()));
  const allUrls = new Set<string>();
  let pagesScraped = 0;

  const csrf = extractCsrf();
  if (!csrf) {
    console.warn('[BestHop] No CSRF token — cannot call Voyager API');
    return { urls: [], pagesScraped: 0, stopped: true, stopReason: 'challenge' };
  }

  // Strip urn prefix if present — the API expects the raw member ID
  const memberId = entityUrn.replace(/^urn:li:fsd_profile:/, '');

  const config = getConfigSync();
  for (let page = 0; page < config.mutualMaxPages; page++) {
    if (signal?.aborted) {
      return { urls: [...allUrls], pagesScraped, stopped: true, stopReason: 'cancelled' };
    }

    // Human-like delay, divided by speed multiplier
    const speed = getSpeed?.() ?? 1;
    try {
      const baseDelay = page === 0
        ? config.mutualFirstPageDelayBaseMs + Math.random() * config.mutualFirstPageDelayRangeMs
        : randomDelay();
      await sleep(baseDelay / speed, signal);
    } catch {
      return { urls: [...allUrls], pagesScraped, stopped: true, stopReason: 'cancelled' };
    }

    const start = page * MUTUAL_PAGE_SIZE;
    const url =
      `https://www.linkedin.com/voyager/api/search/dash/clusters` +
      `?decorationId=${encodeURIComponent(VOYAGER_SEARCH_DECORATION_ID)}` +
      `&origin=MEMBER_PROFILE_CANNED_SEARCH` +
      `&q=all` +
      `&query=(flagshipSearchIntent:SEARCH_SRP,queryParameters:` +
      `(connectionOf:List(${memberId}),network:List(F),resultType:List(PEOPLE)))` +
      `&start=${start}&count=${MUTUAL_PAGE_SIZE}`;

    let data: any;
    try {
      const resp = await fetch(url, {
        headers: {
          'csrf-token': csrf,
          'accept': 'application/vnd.linkedin.normalized+json+2.1',
        },
        credentials: 'include',
        signal,
      });

      if (resp.status === 429) {
        console.warn('[BestHop] LinkedIn 429 — rate limited, auto-downshifting to 1x');
        onSpeedDownshift?.();
        return { urls: [...allUrls], pagesScraped, stopped: true, stopReason: 'challenge' };
      }
      if (resp.status === 403) {
        console.warn('[BestHop] LinkedIn 403 — CSRF expired');
        return { urls: [...allUrls], pagesScraped, stopped: true, stopReason: 'challenge' };
      }
      if (!resp.ok) {
        console.warn(`[BestHop] Voyager search returned ${resp.status}`);
        return { urls: [...allUrls], pagesScraped, stopped: true, stopReason: 'challenge' };
      }

      data = await resp.json();
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return { urls: [...allUrls], pagesScraped, stopped: true, stopReason: 'cancelled' };
      }
      console.warn('[BestHop] Voyager search fetch error:', err);
      return { urls: [...allUrls], pagesScraped, stopped: true, stopReason: 'challenge' };
    }

    pagesScraped++;

    const pageUrls = extractProfileUrlsFromResponse(data, excludeSet);

    console.log(`[BestHop] Page ${page + 1}: ${pageUrls.length} mutual connections`, pageUrls);

    for (const u of pageUrls) {
      allUrls.add(u);
    }

    // Paging metadata
    const total = extractPagingTotal(data);
    const totalPages = total != null ? Math.ceil(total / MUTUAL_PAGE_SIZE) : undefined;
    onProgress(page + 1, totalPages);

    // No results → done
    if (pageUrls.length === 0) {
      return { urls: [...allUrls], pagesScraped, stopped: true, stopReason: 'no_more_results' };
    }

    // Fewer than a full page → last page
    if (pageUrls.length < MUTUAL_PAGE_SIZE) {
      return { urls: [...allUrls], pagesScraped, stopped: false };
    }

  }

  return { urls: [...allUrls], pagesScraped, stopped: true, stopReason: 'max_pages' };
}
