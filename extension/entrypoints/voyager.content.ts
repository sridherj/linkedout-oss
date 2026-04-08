// SPDX-License-Identifier: Apache-2.0
/**
 * MAIN world content script — runs on LinkedIn profile pages.
 * Handles Voyager API calls (same-origin fetch with session cookies)
 * and SPA navigation detection via monkey-patched history API.
 */

import { fetchVoyagerProfile, VoyagerCsrfError, VoyagerRateLimitError, VoyagerChallengePage } from '../lib/voyager/client';
import { extractProfileId, isLinkedInProfilePage } from '../lib/profile/url';
import { getCurrentUserSlug } from '../lib/profile/current-user';
import { extractMutualConnectionUrls } from '../lib/mutual/extractor';
import { getConfigSync } from '../lib/config';
import type {
  VoyagerDataReady, VoyagerDataError, UrlChanged,
  ExtractMutualConnections, MutualExtractionProgress, MutualConnectionsReady,
  SetExtractionSpeed, ExtractionSpeedChanged,
} from '../lib/messages';

// Custom event names (MAIN ↔ bridge communication via document events)
const EVT_URL_CHANGED = 'linkedout:url-changed';
const EVT_VOYAGER_DATA_READY = 'linkedout:voyager-data-ready';
const EVT_VOYAGER_DATA_ERROR = 'linkedout:voyager-data-error';
const EVT_RETRY_FETCH = 'linkedout:retry-fetch';
const EVT_EXTRACT_MUTUAL = 'linkedout:extract-mutual-connections';
const EVT_MUTUAL_PROGRESS = 'linkedout:mutual-extraction-progress';
const EVT_MUTUAL_READY = 'linkedout:mutual-connections-ready';
const EVT_SET_EXTRACTION_SPEED = 'linkedout:set-extraction-speed';
const EVT_EXTRACTION_SPEED_CHANGED = 'linkedout:extraction-speed-changed';

export default defineContentScript({
  matches: ['*://www.linkedin.com/in/*'],
  world: 'MAIN',
  runAt: 'document_idle',

  main() {
    // ── Double-injection guard ──
    if ((window as any).__linkedout) return;
    (window as any).__linkedout = true;

    let lastFetchedProfileId: string | null = null;
    let urlDebounceTimer: ReturnType<typeof setTimeout> | null = null;

    // ── Voyager fetch logic ──
    async function fetchAndDispatch(profileId: string): Promise<void> {
      // Deduplication: skip if we already fetched this profile
      if (profileId === lastFetchedProfileId) return;
      lastFetchedProfileId = profileId;

      try {
        const raw = await fetchVoyagerProfile(profileId);
        const payload: VoyagerDataReady = {
          type: 'VOYAGER_DATA_READY',
          profileId,
          raw,
        };
        document.dispatchEvent(
          new CustomEvent(EVT_VOYAGER_DATA_READY, { detail: payload }),
        );
      } catch (err) {
        let errorType: VoyagerDataError['errorType'] = 'unknown';
        let message = String(err);

        if (err instanceof VoyagerCsrfError) errorType = 'csrf';
        else if (err instanceof VoyagerRateLimitError) errorType = 'rate_limit';
        else if (err instanceof VoyagerChallengePage) errorType = 'challenge';

        const payload: VoyagerDataError = {
          type: 'VOYAGER_DATA_ERROR',
          profileId,
          errorType,
          message,
        };
        document.dispatchEvent(
          new CustomEvent(EVT_VOYAGER_DATA_ERROR, { detail: payload }),
        );
      }
    }

    // ── Handle URL changes (SPA navigation or initial load) ──
    function handleUrlChange(url: string): void {
      if (!isLinkedInProfilePage(url)) return;

      // Dispatch UrlChanged to bridge → SW
      const payload: UrlChanged = { type: 'URL_CHANGED', url };
      document.dispatchEvent(
        new CustomEvent(EVT_URL_CHANGED, { detail: payload }),
      );

      const profileId = extractProfileId(url);
      if (profileId) fetchAndDispatch(profileId);
    }

    /** Debounced URL change: only process the last event within 500ms. */
    function debouncedUrlChange(url: string): void {
      if (urlDebounceTimer) clearTimeout(urlDebounceTimer);
      // Reset dedup so a new navigation always fetches fresh data
      lastFetchedProfileId = null;
      urlDebounceTimer = setTimeout(() => {
        urlDebounceTimer = null;
        handleUrlChange(url);
      }, getConfigSync().urlDebounceMs);
    }

    // ── SPA navigation detection: monkey-patch history API ──
    const originalPushState = history.pushState.bind(history);
    const originalReplaceState = history.replaceState.bind(history);

    history.pushState = function (...args: Parameters<typeof history.pushState>) {
      originalPushState(...args);
      debouncedUrlChange(location.href);
    };

    history.replaceState = function (...args: Parameters<typeof history.replaceState>) {
      originalReplaceState(...args);
      debouncedUrlChange(location.href);
    };

    window.addEventListener('popstate', () => {
      debouncedUrlChange(location.href);
    });

    // ── Listen for RetryFetch from bridge (after challenge cleared) ──
    document.addEventListener(EVT_RETRY_FETCH, (() => {
      lastFetchedProfileId = null;
      handleUrlChange(location.href);
    }) as EventListener);

    // ── Extraction speed state (controlled from side panel via SW → bridge) ──
    let extractionSpeed: 1 | 2 | 4 | 8 = 1;

    document.addEventListener(EVT_SET_EXTRACTION_SPEED, ((e: CustomEvent<SetExtractionSpeed>) => {
      extractionSpeed = e.detail.multiplier;
    }) as EventListener);

    // ── Listen for ExtractMutualConnections from bridge ──
    let mutualAbort: AbortController | null = null;

    document.addEventListener(EVT_EXTRACT_MUTUAL, (async (e: Event) => {
      const { detail } = e as CustomEvent<ExtractMutualConnections>;
      const { entityUrn } = detail;

      // Reset speed to 1x at start of each extraction
      extractionSpeed = 1;

      // Abort any previous extraction
      mutualAbort?.abort();
      mutualAbort = new AbortController();

      try {
        // Collect slugs to exclude: current user + target profile
        const excludeSlugs: string[] = [];
        const currentUserSlug = getCurrentUserSlug();
        if (currentUserSlug) excludeSlugs.push(currentUserSlug);
        const targetSlug = extractProfileId(location.href);
        if (targetSlug) excludeSlugs.push(targetSlug);

        const result = await extractMutualConnectionUrls(
          entityUrn,
          (page, total) => {
            const progress: MutualExtractionProgress = {
              type: 'MUTUAL_EXTRACTION_PROGRESS',
              page,
              total,
            };
            document.dispatchEvent(
              new CustomEvent(EVT_MUTUAL_PROGRESS, { detail: progress }),
            );
          },
          mutualAbort.signal,
          excludeSlugs,
          () => extractionSpeed,
          () => {
            // 429 auto-downshift: reset to 1x and notify side panel
            extractionSpeed = 1;
            const changed: ExtractionSpeedChanged = {
              type: 'EXTRACTION_SPEED_CHANGED',
              multiplier: 1,
            };
            document.dispatchEvent(
              new CustomEvent(EVT_EXTRACTION_SPEED_CHANGED, { detail: changed }),
            );
          },
        );

        const ready: MutualConnectionsReady = {
          type: 'MUTUAL_CONNECTIONS_READY',
          urls: result.urls,
          pagesScraped: result.pagesScraped,
          stopped: result.stopped,
          stopReason: result.stopReason,
        };
        document.dispatchEvent(
          new CustomEvent(EVT_MUTUAL_READY, { detail: ready }),
        );
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        const ready: MutualConnectionsReady = {
          type: 'MUTUAL_CONNECTIONS_READY',
          urls: [],
          pagesScraped: 0,
          stopped: true,
          stopReason: 'challenge',
        };
        document.dispatchEvent(
          new CustomEvent(EVT_MUTUAL_READY, { detail: ready }),
        );
      }
    }) as EventListener);

    // ── Initial load: if already on a profile page, dispatch URL change ──
    handleUrlChange(location.href);
  },
});
