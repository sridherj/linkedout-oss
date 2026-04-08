// SPDX-License-Identifier: Apache-2.0
/**
 * SSE streaming client for Best Hop search.
 * Runs in the service worker context.
 */

import { getConfigSync } from '../config';
import { normalizeLinkedinUrl } from '../profile/url';

// ── Types ───────────────────────────────────────────────────

export interface BestHopParams {
  targetName: string;
  targetUrl: string;
  mutualUrls: string[];
}

export interface BestHopResultData {
  rank: number;
  connectionId: string;
  crawledProfileId: string;
  name: string;
  role?: string;
  reasoning?: string;
  affinityScore?: number;
  linkedinUrl?: string;
}

export interface BestHopDoneData {
  totalResults: number;
  matched: number;
  unmatched: number;
  sessionId?: string;
}

export type BestHopEvent =
  | { type: 'thinking'; message: string }
  | { type: 'result'; data: BestHopResultData }
  | { type: 'done'; data: BestHopDoneData }
  | { type: 'error'; data: { message: string } };

// ── Internal helpers ────────────────────────────────────────

interface SSEPayload {
  type: string;
  message?: string;
  payload?: Record<string, unknown>;
}


export function parseResultPayload(
  payload: Record<string, unknown>,
  rank: number,
): BestHopResultData {
  return {
    rank,
    connectionId: payload.connection_id as string,
    crawledProfileId: payload.crawled_profile_id as string,
    name: payload.full_name as string,
    role: (payload.current_position as string | undefined) ?? undefined,
    reasoning: (payload.why_this_person as string | undefined) ?? undefined,
    affinityScore: (payload.affinity_score as number | undefined) ?? undefined,
    linkedinUrl: (payload.linkedin_url as string | undefined) ?? undefined,
  };
}

// ── Public API ──────────────────────────────────────────────

/**
 * Stream Best Hop search results via SSE.
 * Calls the backend's `/search` endpoint and maps raw SSE events
 * to the simplified BestHopEvent contract for the extension.
 */
export async function streamBestHop(
  params: BestHopParams,
  signal: AbortSignal,
  onEvent: (event: BestHopEvent) => void,
): Promise<void> {
  const config = getConfigSync();
  const url = `${config.backendUrl}/tenants/${config.tenantId}/bus/${config.buId}/best-hop`;

  let res: Response;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-App-User-Id': config.userId,
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({
        target_name: params.targetName,
        target_url: normalizeLinkedinUrl(params.targetUrl) ?? params.targetUrl,
        mutual_urls: params.mutualUrls.map(u => normalizeLinkedinUrl(u) ?? u),
      }),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === 'AbortError') return;
    onEvent({ type: 'error', data: { message: 'Backend is unreachable' } });
    return;
  }

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    onEvent({
      type: 'error',
      data: { message: `${res.status}: ${body || res.statusText}` },
    });
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    onEvent({ type: 'error', data: { message: 'No response body' } });
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';
  let resultRank = 0;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      // Keep the last (possibly incomplete) line in the buffer
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('data: ')) continue;

        const json = trimmed.slice(6);
        if (json === '[DONE]') continue;

        let event: SSEPayload;
        try {
          event = JSON.parse(json);
        } catch {
          continue; // skip malformed lines
        }

        switch (event.type) {
          case 'thinking':
            onEvent({ type: 'thinking', message: event.message ?? '' });
            break;

          case 'result':
            if (event.payload) {
              resultRank++;
              onEvent({
                type: 'result',
                data: parseResultPayload(event.payload, resultRank),
              });
            }
            break;

          case 'explanations':
            // Explanation data arrives after results — ignored for now.
            // The orchestrator in sp3c can merge explanations if needed.
            break;

          case 'done':
            onEvent({
              type: 'done',
              data: {
                totalResults:
                  (event.payload?.total as number | undefined) ?? resultRank,
                matched: (event.payload?.matched as number | undefined) ?? 0,
                unmatched: (event.payload?.unmatched as number | undefined) ?? 0,
                sessionId: (event.payload?.session_id as string | undefined) ?? undefined,
              },
            });
            break;

          case 'error':
            onEvent({
              type: 'error',
              data: { message: event.message ?? 'Search failed' },
            });
            break;

          case 'heartbeat':
          case 'session':
          case 'conversation_state':
            // Not relevant for Best Hop — skip
            break;
        }
      }
    }
  } catch (err) {
    if ((err as Error).name === 'AbortError') return;
    onEvent({
      type: 'error',
      data: { message: (err as Error).message || 'Stream read failed' },
    });
  } finally {
    reader.releaseLock();
  }
}
