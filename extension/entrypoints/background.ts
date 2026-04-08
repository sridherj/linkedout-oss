// SPDX-License-Identifier: Apache-2.0
/**
 * Service worker — the orchestration hub.
 * All decision logic (freshness, rate limiting, mode checks) lives here.
 * Content scripts and side panel are thin data-fetchers/renderers.
 */

import { browser } from 'wxt/browser';
import { parseVoyagerProfile } from '../lib/voyager/parser';
import { toCrawledProfilePayload, toEnrichPayload } from '../lib/profile/mapper';
import { isLinkedInProfilePage, extractProfileId } from '../lib/profile/url';
import { checkFreshness, createProfile, updateProfile, enrichProfile as enrichProfileBackend, BackendUnreachable, BackendError } from '../lib/backend/client';
import { canProceed, record, getStatus } from '../lib/rate-limiter';
import { getEnrichmentMode, onEnrichmentModeChange } from '../lib/settings';
import { appendLog, type LogEntry } from '../lib/log';
import { streamBestHop } from '../lib/backend/search';
import { initConfig, getConfigSync } from '../lib/config';
import type { FreshnessResult } from '../lib/backend/client';
import type { ProfileBadgeStatus } from '../lib/messages';
import type {
  ExtensionMessage,
  ProfileStatusUpdate,
  ProfileDisplayData,
  RateLimitUpdate,
  LogUpdated,
  VoyagerDataReady,
  VoyagerDataError,
  UrlChanged,
  RetryFetch,
  FindBestHop,
  ExtractMutualConnections,
  MutualConnectionsReady,
  MutualExtractionProgress,
  BestHopResult,
  BestHopThinking,
  BestHopComplete,
  BestHopError,
  OfflineStatusUpdate,
  ChallengeStatusUpdate,
  ExtractionSpeedChanged,
} from '../lib/messages';

export default defineBackground(() => {
  // ── Initialize runtime config (loads from browser.storage.local) ──
  initConfig();

  // ── Side panel registration ──
  browser.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

  // ── Ephemeral state ──
  let currentTabUrl: string | null = null;
  let currentProfileId: string | null = null;
  let processingProfileId: string | null = null;
  let enrichmentMode: 'manual' | 'auto' = 'manual';

  // ── Error badge state ──
  let errorCount = 0;

  function incrementErrorBadge(): void {
    errorCount++;
    browser.action.setBadgeText({ text: String(errorCount) });
    browser.action.setBadgeBackgroundColor({ color: '#dc2626' });
  }

  function clearErrorBadge(): void {
    errorCount = 0;
    browser.action.setBadgeText({ text: '' });
  }

  // ── Freshness check promise (started at URL_CHANGED, consumed in processVoyagerData) ──
  let freshnessPromise: Promise<FreshnessResult> | null = null;

  // ── Cached parsed result for side panel display + manual Fetch button ──
  let lastParsedResult: {
    profile: NonNullable<ReturnType<typeof parseVoyagerProfile>>;
    profileId: string;
    profileData: ProfileDisplayData;
    resolvedStatus?: {
      badgeStatus: ProfileBadgeStatus;
      crawledProfileId?: string;
      staleDays?: number;
    };
  } | null = null;

  // ── Error hardening state ──
  let isOffline = false;
  let challengeActive = false;
  let pipelineAbort: AbortController | null = null;

  // ── Enrichment dedup lock ──
  const enrichingIds = new Set<string>();

  /** Skip duplicate enrichProfileBackend calls while one is in-flight. */
  async function enrichProfileGuarded(
    id: string,
    payload: ReturnType<typeof toEnrichPayload>,
  ): Promise<void> {
    if (enrichingIds.has(id)) return;
    enrichingIds.add(id);
    try {
      await enrichProfileGuarded(id, payload);
    } finally {
      enrichingIds.delete(id);
    }
  }

  // ── Best Hop state ──
  let bestHopAbort: AbortController | null = null;

  // Load initial mode
  getEnrichmentMode().then((mode) => { enrichmentMode = mode; });
  onEnrichmentModeChange((mode) => { enrichmentMode = mode; });

  // ── Helpers ──

  function broadcastToSidePanel(message: ExtensionMessage): void {
    browser.runtime.sendMessage(message).catch(() => {
      // Side panel not open — ignore
    });
  }

  async function appendLogAndNotify(entry: LogEntry): Promise<void> {
    await appendLog(entry);
    if (entry.action === 'error') incrementErrorBadge();
    const update: LogUpdated = { type: 'LOG_UPDATED', entry };
    broadcastToSidePanel(update);
  }

  async function sendRateLimitUpdate(): Promise<void> {
    const status = await getStatus();
    const update: RateLimitUpdate = {
      type: 'RATE_LIMIT_UPDATE',
      hourly: status.hourly,
      daily: status.daily,
    };
    broadcastToSidePanel(update);
  }

  function sendProfileStatus(
    status: ProfileStatusUpdate['status'],
    opts?: Partial<Omit<ProfileStatusUpdate, 'type' | 'status'>>,
  ): void {
    const update: ProfileStatusUpdate = { type: 'PROFILE_STATUS_UPDATE', status, ...opts };
    broadcastToSidePanel(update);
  }

  // ── Error hardening helpers ──

  function setOffline(offline: boolean): void {
    if (isOffline === offline) return;
    isOffline = offline;
    const update: OfflineStatusUpdate = { type: 'OFFLINE_STATUS_UPDATE', isOffline: offline };
    broadcastToSidePanel(update);
  }

  function setChallenge(active: boolean, message?: string): void {
    if (challengeActive === active) return;
    challengeActive = active;
    const update: ChallengeStatusUpdate = { type: 'CHALLENGE_STATUS_UPDATE', isActive: active, message };
    broadcastToSidePanel(update);
  }

  /** Mark backend as reachable on any successful backend call. */
  function markBackendReachable(): void {
    if (isOffline) setOffline(false);
  }

  /** Cancel in-flight pipeline operation. */
  function cancelPipeline(): void {
    pipelineAbort?.abort();
    pipelineAbort = new AbortController();
  }

  // ── Core enrichment pipeline (called when VoyagerDataReady arrives) ──

  async function processVoyagerData(data: VoyagerDataReady): Promise<void> {
    const { profileId, raw } = data;

    // Stale check: if user navigated away, drop this result
    if (profileId !== currentProfileId) {
      return;
    }

    // On successful Voyager response, clear challenge flag
    if (challengeActive) setChallenge(false);

    processingProfileId = profileId;

    // 1. Parse
    const profile = parseVoyagerProfile(raw as any);
    if (!profile) {
      sendProfileStatus('error', { errorMessage: 'Failed to parse Voyager response' });
      await appendLogAndNotify({
        timestamp: new Date().toISOString(),
        action: 'error',
        linkedinUrl: currentTabUrl ?? undefined,
        reason: 'Failed to parse Voyager response',
      });
      return;
    }

    const profileName = [profile.firstName, profile.lastName].filter(Boolean).join(' ');
    const linkedinUrl = `https://www.linkedin.com/in/${profileId}`;
    const profileData: ProfileDisplayData = {
      name: profileName,
      headline: profile.headline || null,
      avatarUrl: profile.profilePicture || null,
      location: profile.locationName || null,
      connectionsCount: profile.connectionsCount ?? null,
      openToWork: profile.openToWork,
      linkedinUrl,
      entityUrn: profile.entityUrn || null,
    };

    // Cache parsed result for Fetch button and side panel open
    lastParsedResult = { profile, profileId, profileData };

    // Always send profile data for display
    sendProfileStatus('ready', {
      profileName,
      profileHeadline: profile.headline,
      linkedinUrl,
      profileData,
    });

    if (enrichmentMode === 'manual') {
      // Await the freshness check started at URL_CHANGED time
      const freshness = freshnessPromise ? await freshnessPromise : null;

      // Preserve offline detection: if freshness came back with offline flag, surface it
      if (freshness && 'offline' in freshness && freshness.offline) {
        setOffline(true);
      } else if (freshness) {
        markBackendReachable();
      }

      if (!freshness || !freshness.exists) {
        lastParsedResult!.resolvedStatus = { badgeStatus: 'not_saved' };
        sendProfileStatus('ready', {
          badgeStatus: 'not_saved',
          profileName, profileHeadline: profile.headline, linkedinUrl, profileData,
        });
      } else if (freshness.staleDays < getConfigSync().stalenessDays) {
        // Backfill enrichment if missing
        if (!freshness.profile.has_enriched_data) {
          try { await enrichProfileGuarded(freshness.id, toEnrichPayload(profile)); } catch {}
        }
        lastParsedResult!.resolvedStatus = { badgeStatus: 'up_to_date', crawledProfileId: freshness.id, staleDays: freshness.staleDays };
        sendProfileStatus('skipped', {
          badgeStatus: 'up_to_date',
          profileName, profileHeadline: profile.headline, linkedinUrl,
          crawledProfileId: freshness.id, profileData, staleDays: freshness.staleDays,
        });
      } else {
        lastParsedResult!.resolvedStatus = { badgeStatus: 'stale', crawledProfileId: freshness.id, staleDays: freshness.staleDays };
        sendProfileStatus('ready', {
          badgeStatus: 'stale',
          profileName, profileHeadline: profile.headline, linkedinUrl,
          crawledProfileId: freshness.id, profileData, staleDays: freshness.staleDays,
        });
      }
      processingProfileId = null;
      return;
    }

    // Auto mode — run enrichment pipeline
    await enrichProfile(profile, profileId, profileData);
  }

  /** Enrichment pipeline: rate limit → freshness → save to backend. */
  async function enrichProfile(
    profile: NonNullable<ReturnType<typeof parseVoyagerProfile>>,
    profileId: string,
    profileData: ProfileDisplayData,
  ): Promise<void> {
    const profileName = profileData.name;
    const linkedinUrl = profileData.linkedinUrl;

    // Check rate limit
    const allowed = await canProceed();
    if (!allowed) {
      sendProfileStatus('error', {
        badgeStatus: 'rate_limited',
        profileName,
        profileHeadline: profile.headline,
        linkedinUrl,
        errorMessage: 'Rate limited',
        profileData,
      });
      await appendLogAndNotify({
        timestamp: new Date().toISOString(),
        action: 'rate_limited',
        profileName,
        profileHeadline: profile.headline,
        linkedinUrl,
        reason: 'Hourly or daily rate limit reached',
      });
      await sendRateLimitUpdate();
      return;
    }

    sendProfileStatus('saving', { profileName, profileHeadline: profile.headline, linkedinUrl, profileData });

    // Check freshness and save
    try {
      const freshness = await checkFreshness(linkedinUrl);
      markBackendReachable();
      const payload = toCrawledProfilePayload(profile, profileId);

      if (!freshness.exists) {
        // New profile → create (with 409 race condition handling)
        try {
          const newId = await createProfile(payload);
          markBackendReachable();
          await record();
          try {
            await enrichProfileGuarded(newId, toEnrichPayload(profile));
          } catch (enrichErr) {
            console.warn('[enrichProfile] Failed:', enrichErr);
            await appendLogAndNotify({
              timestamp: new Date().toISOString(),
              action: 'error',
              profileName, linkedinUrl,
              reason: `Enrichment failed: ${enrichErr}`,
            });
          }
          if (lastParsedResult) lastParsedResult.resolvedStatus = { badgeStatus: 'saved_today', crawledProfileId: newId };
          sendProfileStatus('done', {
            badgeStatus: 'saved_today',
            profileName,
            profileHeadline: profile.headline,
            linkedinUrl,
            crawledProfileId: newId,
            profileData,
          });
          await appendLogAndNotify({
            timestamp: new Date().toISOString(),
            action: 'saved',
            profileName,
            profileHeadline: profile.headline,
            linkedinUrl,
            reason: 'New profile created',
          });
        } catch (createErr) {
          // 409 unique constraint → race condition, treat as update
          if (createErr instanceof BackendError && createErr.status === 409) {
            const retryFreshness = await checkFreshness(linkedinUrl);
            markBackendReachable();
            if (retryFreshness.exists) {
              await updateProfile(retryFreshness.id, payload);
              markBackendReachable();
              await record();
              try {
                await enrichProfileGuarded(retryFreshness.id, toEnrichPayload(profile));
              } catch (enrichErr) {
                console.warn('[enrichProfile] Failed:', enrichErr);
                await appendLogAndNotify({
                  timestamp: new Date().toISOString(),
                  action: 'error',
                  profileName, linkedinUrl,
                  reason: `Enrichment failed: ${enrichErr}`,
                });
              }
              if (lastParsedResult) lastParsedResult.resolvedStatus = { badgeStatus: 'saved_today', crawledProfileId: retryFreshness.id };
              sendProfileStatus('done', {
                badgeStatus: 'saved_today',
                profileName,
                profileHeadline: profile.headline,
                linkedinUrl,
                crawledProfileId: retryFreshness.id,
                profileData,
              });
              await appendLogAndNotify({
                timestamp: new Date().toISOString(),
                action: 'updated',
                profileName,
                profileHeadline: profile.headline,
                linkedinUrl,
                reason: 'Create race condition → updated existing profile',
              });
            }
          } else {
            throw createErr; // re-throw non-409 errors
          }
        }
      } else if (freshness.staleDays < getConfigSync().stalenessDays) {
        // Fresh → skip, but backfill enrichment if missing (Q10)
        if (!freshness.profile.has_enriched_data) {
          try {
            await enrichProfileGuarded(freshness.id, toEnrichPayload(profile));
          } catch (enrichErr) {
            console.warn('[enrichProfile] Backfill failed:', enrichErr);
          }
        }
        if (lastParsedResult) lastParsedResult.resolvedStatus = { badgeStatus: 'up_to_date', crawledProfileId: freshness.id, staleDays: freshness.staleDays };
        sendProfileStatus('skipped', {
          badgeStatus: 'up_to_date',
          profileName,
          profileHeadline: profile.headline,
          linkedinUrl,
          crawledProfileId: freshness.id,
          profileData,
          staleDays: freshness.staleDays,
        });
        await appendLogAndNotify({
          timestamp: new Date().toISOString(),
          action: 'skipped',
          profileName,
          profileHeadline: profile.headline,
          linkedinUrl,
          reason: `Profile is fresh (${freshness.staleDays} days old)`,
        });
      } else {
        // Stale → update
        await updateProfile(freshness.id, payload);
        markBackendReachable();
        await record();
        try {
          await enrichProfileGuarded(freshness.id, toEnrichPayload(profile));
        } catch (enrichErr) {
          console.warn('[enrichProfile] Failed:', enrichErr);
          await appendLogAndNotify({
            timestamp: new Date().toISOString(),
            action: 'error',
            profileName, linkedinUrl,
            reason: `Enrichment failed: ${enrichErr}`,
          });
        }
        if (lastParsedResult) lastParsedResult.resolvedStatus = { badgeStatus: 'saved_today', crawledProfileId: freshness.id };
        sendProfileStatus('done', {
          badgeStatus: 'saved_today',
          profileName,
          profileHeadline: profile.headline,
          linkedinUrl,
          crawledProfileId: freshness.id,
          profileData,
        });
        await appendLogAndNotify({
          timestamp: new Date().toISOString(),
          action: 'updated',
          profileName,
          profileHeadline: profile.headline,
          linkedinUrl,
          reason: `Profile was stale (${freshness.staleDays} days old)`,
        });
      }
    } catch (err) {
      if (lastParsedResult) lastParsedResult.resolvedStatus = { badgeStatus: 'save_failed' };
      if (err instanceof BackendUnreachable) {
        setOffline(true);
        sendProfileStatus('error', {
          badgeStatus: 'save_failed',
          profileName,
          profileHeadline: profile.headline,
          linkedinUrl,
          errorMessage: 'Backend is unreachable',
          profileData,
        });
      } else {
        sendProfileStatus('error', {
          badgeStatus: 'save_failed',
          profileName,
          profileHeadline: profile.headline,
          linkedinUrl,
          errorMessage: String(err),
          profileData,
        });
      }
      await appendLogAndNotify({
        timestamp: new Date().toISOString(),
        action: 'error',
        profileName,
        profileHeadline: profile.headline,
        linkedinUrl,
        reason: err instanceof BackendUnreachable ? 'Backend is unreachable' : String(err),
      });
    }

    await sendRateLimitUpdate();
    processingProfileId = null;
  }

  // ── Handle Voyager errors from MAIN world ──

  async function handleVoyagerError(data: VoyagerDataError): Promise<void> {
    const { profileId, errorType, message } = data;
    if (profileId !== currentProfileId) return;

    // Challenge detection → pause all automated Voyager calls
    if (errorType === 'challenge') {
      setChallenge(true, 'LinkedIn detected unusual activity. Please complete the challenge in your LinkedIn tab, then click Retry.');
      await appendLogAndNotify({
        timestamp: new Date().toISOString(),
        action: 'error',
        linkedinUrl: currentTabUrl ?? undefined,
        reason: 'LinkedIn challenge detected',
      });
      sendProfileStatus('error', {
        badgeStatus: 'challenge_detected',
        linkedinUrl: currentTabUrl ?? undefined,
        errorMessage: 'LinkedIn challenge detected — solve CAPTCHA and retry',
      });
      return;
    }

    // LinkedIn 429 → back off, do NOT count against self-imposed limits
    if (errorType === 'rate_limit') {
      await appendLogAndNotify({
        timestamp: new Date().toISOString(),
        action: 'rate_limited',
        linkedinUrl: currentTabUrl ?? undefined,
        reason: 'LinkedIn 429',
      });
      sendProfileStatus('error', {
        badgeStatus: 'save_failed',
        linkedinUrl: currentTabUrl ?? undefined,
        errorMessage: 'LinkedIn is rate limiting requests. Slow down and try again later.',
      });
      return;
    }

    // CSRF expiry → tell user to refresh
    if (errorType === 'csrf') {
      await appendLogAndNotify({
        timestamp: new Date().toISOString(),
        action: 'error',
        linkedinUrl: currentTabUrl ?? undefined,
        reason: 'CSRF token expired',
      });
      sendProfileStatus('error', {
        badgeStatus: 'save_failed',
        linkedinUrl: currentTabUrl ?? undefined,
        errorMessage: 'LinkedIn session expired. Please refresh the LinkedIn page.',
      });
      return;
    }

    // Generic error
    sendProfileStatus('error', {
      badgeStatus: 'save_failed',
      linkedinUrl: currentTabUrl ?? undefined,
      errorMessage: message,
    });
    await appendLogAndNotify({
      timestamp: new Date().toISOString(),
      action: 'error',
      linkedinUrl: currentTabUrl ?? undefined,
      reason: `Voyager error: ${errorType} — ${message}`,
    });
  }

  // ── Best Hop orchestration ──

  function relayToContentScript(tabId: number, message: ExtensionMessage): void {
    browser.tabs.sendMessage(tabId, message).catch(() => {
      // Content script not ready
    });
  }

  async function handleFindBestHop(data: FindBestHop): Promise<void> {
    // Abort any in-flight best hop search
    bestHopAbort?.abort();
    bestHopAbort = new AbortController();
    const { signal } = bestHopAbort;

    const { entityUrn, linkedinUrl, profileName } = data;

    // Phase 1: Relay extraction request to content script → MAIN world
    const tabs = await browser.tabs.query({ active: true, currentWindow: true });
    const tabId = tabs[0]?.id;
    if (tabId == null) {
      const error: BestHopError = { type: 'BEST_HOP_ERROR', phase: 'extraction', message: 'No active LinkedIn tab found' };
      broadcastToSidePanel(error);
      return;
    }

    const extractMsg: ExtractMutualConnections = { type: 'EXTRACT_MUTUAL_CONNECTIONS', entityUrn };
    relayToContentScript(tabId, extractMsg);

    // Wait for MutualConnectionsReady or cancellation via a one-shot listener
    const mutualResult = await new Promise<MutualConnectionsReady | null>((resolve) => {
      if (signal.aborted) { resolve(null); return; }

      const onAbort = () => resolve(null);
      signal.addEventListener('abort', onAbort, { once: true });

      const handler = (message: ExtensionMessage) => {
        if (message.type === 'MUTUAL_EXTRACTION_PROGRESS') {
          // Forward extraction progress to side panel
          broadcastToSidePanel(message);
        } else if (message.type === 'MUTUAL_CONNECTIONS_READY') {
          signal.removeEventListener('abort', onAbort);
          browser.runtime.onMessage.removeListener(handler);
          resolve(message);
        }
      };
      browser.runtime.onMessage.addListener(handler);
    });

    // Log extracted mutual connections for debugging
    console.log('[BestHop] Mutual connections extracted:', {
      count: mutualResult?.urls.length ?? 0,
      urls: mutualResult?.urls,
      pagesScraped: mutualResult?.pagesScraped,
      stopped: mutualResult?.stopped,
      stopReason: mutualResult?.stopReason,
    });

    // Cancelled during extraction
    if (!mutualResult || signal.aborted) {
      const complete: BestHopComplete = { type: 'BEST_HOP_COMPLETE', totalResults: 0, matched: 0, unmatched: 0 };
      broadcastToSidePanel(complete);
      return;
    }

    // Check for challenge during extraction
    if (mutualResult.stopReason === 'challenge' && mutualResult.urls.length === 0) {
      const error: BestHopError = {
        type: 'BEST_HOP_ERROR',
        phase: 'extraction',
        message: 'LinkedIn challenge detected — solve CAPTCHA and retry',
      };
      broadcastToSidePanel(error);
      return;
    }

    // Zero mutual connections
    if (mutualResult.urls.length === 0) {
      const complete: BestHopComplete = { type: 'BEST_HOP_COMPLETE', totalResults: 0, matched: 0, unmatched: 0 };
      broadcastToSidePanel(complete);
      await appendLogAndNotify({
        timestamp: new Date().toISOString(),
        action: 'best_hop',
        profileName,
        linkedinUrl,
        reason: 'No mutual connections found',
      });
      return;
    }

    // Phase 2: Stream search results via SSE
    let totalResults = 0;
    await streamBestHop(
      {
        targetName: profileName,
        targetUrl: linkedinUrl,
        mutualUrls: mutualResult.urls,
      },
      signal,
      (event) => {
        if (signal.aborted) return;

        switch (event.type) {
          case 'result': {
            totalResults++;
            const result: BestHopResult = {
              type: 'BEST_HOP_RESULT',
              rank: event.data.rank,
              name: event.data.name,
              role: event.data.role ?? null,
              affinityScore: event.data.affinityScore ?? null,
              reasoning: event.data.reasoning ?? null,
              linkedinUrl: event.data.linkedinUrl ?? null,
            };
            broadcastToSidePanel(result);
            break;
          }
          case 'done': {
            const complete: BestHopComplete = {
              type: 'BEST_HOP_COMPLETE',
              totalResults: event.data.totalResults,
              matched: event.data.matched,
              unmatched: event.data.unmatched,
            };
            broadcastToSidePanel(complete);
            break;
          }
          case 'error': {
            const error: BestHopError = { type: 'BEST_HOP_ERROR', phase: 'search', message: event.data.message };
            broadcastToSidePanel(error);
            break;
          }
          case 'thinking': {
            const thinking: BestHopThinking = { type: 'BEST_HOP_THINKING', message: event.message };
            broadcastToSidePanel(thinking);
            break;
          }
        }
      },
    );

    // If SSE ended without a 'done' event (e.g. stream just closed), send completion
    if (!signal.aborted) {
      await appendLogAndNotify({
        timestamp: new Date().toISOString(),
        action: 'best_hop',
        profileName,
        linkedinUrl,
        reason: `${mutualResult.urls.length} mutual → ${totalResults} paths`,
      });
    }

    bestHopAbort = null;
  }

  function handleCancelBestHop(): void {
    if (bestHopAbort) {
      bestHopAbort.abort();
      bestHopAbort = null;
      const complete: BestHopComplete = { type: 'BEST_HOP_COMPLETE', totalResults: 0, matched: 0, unmatched: 0 };
      broadcastToSidePanel(complete);
    }
  }

  // ── Handle URL changes from content script ──

  async function handleUrlChanged(data: UrlChanged): Promise<void> {
    const { url } = data;
    currentTabUrl = url;

    // Cancel any in-flight pipeline operation on navigation
    cancelPipeline();
    lastParsedResult = null;
    freshnessPromise = null;

    if (!isLinkedInProfilePage(url)) {
      currentProfileId = null;
      sendProfileStatus('idle');
      return;
    }

    const profileId = extractProfileId(url);
    if (!profileId) return;
    currentProfileId = profileId;

    sendProfileStatus('fetching', { linkedinUrl: url });
    await sendRateLimitUpdate();

    // Start freshness check in parallel with Voyager fetch
    const linkedinUrl = `https://www.linkedin.com/in/${profileId}`;
    freshnessPromise = checkFreshness(linkedinUrl).catch((err) => {
      if (err instanceof BackendUnreachable) return { exists: false, offline: true } as FreshnessResult;
      return { exists: false } as FreshnessResult;
    });
  }

  // ── Retry after challenge ──

  async function handleRetryAfterChallenge(): Promise<void> {
    setChallenge(false);
    // Ask content script to re-sense (reset dedup + re-fetch)
    if (currentProfileId) {
      sendProfileStatus('fetching', { linkedinUrl: currentTabUrl ?? undefined });
      const tabs = await browser.tabs.query({ active: true, currentWindow: true });
      const tab = tabs[0];
      if (tab?.id != null) {
        const msg: RetryFetch = { type: 'RETRY_FETCH' };
        browser.tabs.sendMessage(tab.id, msg).catch(() => {});
      }
    }
  }

  // ── Message listener ──

  browser.runtime.onMessage.addListener((message: ExtensionMessage) => {
    switch (message.type) {
      case 'URL_CHANGED':
        handleUrlChanged(message);
        break;

      case 'VOYAGER_DATA_READY':
        processVoyagerData(message);
        break;

      case 'VOYAGER_DATA_ERROR':
        handleVoyagerError(message);
        break;

      case 'ENRICH_PROFILE':
        // From side panel — user clicked Fetch in manual mode
        if (lastParsedResult && lastParsedResult.profileId === currentProfileId) {
          const { profile, profileId, profileData } = lastParsedResult;
          sendProfileStatus('saving', {
            profileName: profileData.name,
            profileHeadline: profile.headline,
            linkedinUrl: profileData.linkedinUrl,
            profileData,
          });
          enrichProfile(profile, profileId, profileData);
        }
        break;

      case 'FIND_BEST_HOP':
        handleFindBestHop(message);
        break;

      case 'CANCEL_BEST_HOP':
        handleCancelBestHop();
        break;

      case 'SET_EXTRACTION_SPEED':
        // Relay to content script (MAIN world) and confirm to side panel
        browser.tabs.query({ active: true, currentWindow: true }).then((tabs) => {
          const tab = tabs[0];
          if (tab?.id != null) {
            browser.tabs.sendMessage(tab.id, message).catch(() => {});
          }
        });
        broadcastToSidePanel({
          type: 'EXTRACTION_SPEED_CHANGED',
          multiplier: message.multiplier,
        } satisfies ExtractionSpeedChanged);
        break;

      case 'EXTRACTION_SPEED_CHANGED':
        // From MAIN world (429 auto-downshift) → forward to side panel
        broadcastToSidePanel(message);
        break;

      case 'RETRY_AFTER_CHALLENGE':
        handleRetryAfterChallenge();
        break;
    }
  });

  // ── Tab URL change fallback ──
  // Content scripts may miss SPA navigations (timing, guard). This catches URL
  // changes at the browser level so the side panel always stays in sync.
  browser.tabs.onUpdated.addListener((_tabId, changeInfo, tab) => {
    if (changeInfo.url && tab.active) {
      const url = changeInfo.url;
      // Only handle if URL actually changed from what we're tracking
      if (url !== currentTabUrl) {
        handleUrlChanged({ type: 'URL_CHANGED', url });
      }
    }
  });

  // ── Side panel connect signal ──

  browser.runtime.onConnect.addListener((port) => {
    // Side panel opened — clear error badge
    clearErrorBadge();

    // Send current error hardening state
    if (isOffline) {
      broadcastToSidePanel({ type: 'OFFLINE_STATUS_UPDATE', isOffline: true } satisfies OfflineStatusUpdate);
    }
    if (challengeActive) {
      broadcastToSidePanel({
        type: 'CHALLENGE_STATUS_UPDATE',
        isActive: true,
        message: 'LinkedIn detected unusual activity. Please complete the challenge in your LinkedIn tab, then click Retry.',
      } satisfies ChallengeStatusUpdate);
    }

    // Send cached profile if available, otherwise query active tab state
    if (lastParsedResult && lastParsedResult.profileId === currentProfileId) {
      const { profile, profileData, resolvedStatus } = lastParsedResult;
      sendProfileStatus(resolvedStatus ? (resolvedStatus.badgeStatus === 'up_to_date' ? 'skipped' : 'ready') : 'ready', {
        profileName: profileData.name,
        profileHeadline: profile.headline,
        linkedinUrl: profileData.linkedinUrl,
        profileData,
        ...(resolvedStatus && {
          badgeStatus: resolvedStatus.badgeStatus,
          crawledProfileId: resolvedStatus.crawledProfileId,
          staleDays: resolvedStatus.staleDays,
        }),
      });
      sendRateLimitUpdate();
    } else {
      // No cached data — check if we're on a profile page and wait for content script
      browser.tabs.query({ active: true, currentWindow: true }).then(async (tabs) => {
        const tab = tabs[0];
        const tabUrl = tab?.url ?? '';
        if (isLinkedInProfilePage(tabUrl)) {
          currentTabUrl = tabUrl;
          currentProfileId = extractProfileId(tabUrl);
          sendProfileStatus('fetching', { linkedinUrl: tabUrl });
        } else {
          sendProfileStatus('idle');
        }
        await sendRateLimitUpdate();
      });
    }
  });

});
