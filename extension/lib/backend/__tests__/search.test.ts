// SPDX-License-Identifier: Apache-2.0
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { parseResultPayload, streamBestHop } from '../search';
import type { BestHopParams, BestHopEvent } from '../search';

// ── Mocks ──────────────────────────────────────────────────

const mockFetch = vi.fn();

beforeEach(() => {
  mockFetch.mockReset();
  vi.stubGlobal('fetch', mockFetch);
});

afterEach(() => {
  vi.restoreAllMocks();
});

/** Build a ReadableStream from an array of SSE lines. */
function sseStream(lines: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const chunks = lines.map(l => encoder.encode(l + '\n'));
  let i = 0;
  return new ReadableStream({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(chunks[i++]);
      } else {
        controller.close();
      }
    },
  });
}

function sseResponse(lines: string[], status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: 'OK',
    body: sseStream(lines),
    text: () => Promise.resolve(lines.join('\n')),
  } as unknown as Response;
}

function collectEvents(lines: string[], signal?: AbortSignal): Promise<BestHopEvent[]> {
  const events: BestHopEvent[] = [];
  const params: BestHopParams = {
    targetName: 'Jane',
    targetUrl: 'https://www.linkedin.com/in/jane',
    mutualUrls: ['https://www.linkedin.com/in/alice'],
  };
  mockFetch.mockResolvedValueOnce(sseResponse(lines));
  return streamBestHop(params, signal ?? new AbortController().signal, e => events.push(e))
    .then(() => events);
}

// ── parseResultPayload ─────────────────────────────────────

describe('parseResultPayload', () => {
  it('maps snake_case → camelCase fields', () => {
    const result = parseResultPayload(
      {
        connection_id: 'conn_1',
        crawled_profile_id: 'cp_1',
        full_name: 'Alice',
        current_position: 'Engineer',
        why_this_person: 'Strong tie',
        affinity_score: 0.9,
        linkedin_url: 'https://www.linkedin.com/in/alice',
      },
      1,
    );
    expect(result).toEqual({
      rank: 1,
      connectionId: 'conn_1',
      crawledProfileId: 'cp_1',
      name: 'Alice',
      role: 'Engineer',
      reasoning: 'Strong tie',
      affinityScore: 0.9,
      linkedinUrl: 'https://www.linkedin.com/in/alice',
    });
  });

  it('handles missing optional fields', () => {
    const result = parseResultPayload(
      { connection_id: 'conn_2', crawled_profile_id: 'cp_2', full_name: 'Bob' },
      3,
    );
    expect(result.rank).toBe(3);
    expect(result.role).toBeUndefined();
    expect(result.reasoning).toBeUndefined();
    expect(result.affinityScore).toBeUndefined();
  });
});

// ── streamBestHop ──────────────────────────────────────────

describe('streamBestHop', () => {
  it('POSTs to /tenants/{tenant_id}/bus/{bu_id}/best-hop', async () => {
    mockFetch.mockResolvedValueOnce(sseResponse([]));
    const params: BestHopParams = {
      targetName: 'Jane',
      targetUrl: 'https://www.linkedin.com/in/jane',
      mutualUrls: [],
    };

    await streamBestHop(params, new AbortController().signal, () => {});

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/tenants\/[^/]+\/bus\/[^/]+\/best-hop$/);
    expect(init.method).toBe('POST');
  });

  it('sends structured body with target_name, target_url, mutual_urls', async () => {
    mockFetch.mockResolvedValueOnce(sseResponse([]));
    const params: BestHopParams = {
      targetName: 'Jane',
      targetUrl: 'https://www.linkedin.com/in/jane',
      mutualUrls: ['https://www.linkedin.com/in/alice'],
    };

    await streamBestHop(params, new AbortController().signal, () => {});

    const [, init] = mockFetch.mock.calls[0];
    const body = JSON.parse(init.body);
    expect(body).toEqual({
      target_name: 'Jane',
      target_url: 'https://www.linkedin.com/in/jane',
      mutual_urls: ['https://www.linkedin.com/in/alice'],
    });
  });

  it('sends correct headers', async () => {
    mockFetch.mockResolvedValueOnce(sseResponse([]));
    const params: BestHopParams = {
      targetName: 'Jane',
      targetUrl: 'https://www.linkedin.com/in/jane',
      mutualUrls: [],
    };

    await streamBestHop(params, new AbortController().signal, () => {});

    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(init.headers['X-App-User-Id']).toBeDefined();
    expect(init.headers['Accept']).toBe('text/event-stream');
  });

  it('emits thinking event', async () => {
    const events = await collectEvents([
      'data: {"type":"thinking","message":"Analyzing..."}',
    ]);
    expect(events).toEqual([{ type: 'thinking', message: 'Analyzing...' }]);
  });

  it('emits result events with auto-incrementing rank', async () => {
    const events = await collectEvents([
      'data: {"type":"result","payload":{"connection_id":"c1","crawled_profile_id":"cp1","full_name":"Alice"}}',
      'data: {"type":"result","payload":{"connection_id":"c2","crawled_profile_id":"cp2","full_name":"Bob"}}',
    ]);
    const results = events.filter(e => e.type === 'result');
    expect(results).toHaveLength(2);
    expect((results[0] as { type: 'result'; data: { rank: number } }).data.rank).toBe(1);
    expect((results[1] as { type: 'result'; data: { rank: number } }).data.rank).toBe(2);
  });

  it('emits done with totalResults, matched, and unmatched', async () => {
    const events = await collectEvents([
      'data: {"type":"done","payload":{"total":5,"matched":18,"unmatched":6,"session_id":"sess_123"}}',
    ]);
    expect(events).toEqual([{
      type: 'done',
      data: { totalResults: 5, matched: 18, unmatched: 6, sessionId: 'sess_123' },
    }]);
  });

  it('defaults matched/unmatched to 0 when not present', async () => {
    const events = await collectEvents([
      'data: {"type":"done","payload":{"total":3}}',
    ]);
    expect(events).toEqual([{
      type: 'done',
      data: { totalResults: 3, matched: 0, unmatched: 0, sessionId: undefined },
    }]);
  });

  it('emits error event', async () => {
    const events = await collectEvents([
      'data: {"type":"error","message":"Something broke"}',
    ]);
    expect(events).toEqual([{ type: 'error', data: { message: 'Something broke' } }]);
  });

  it('skips heartbeat, session, conversation_state', async () => {
    const events = await collectEvents([
      'data: {"type":"heartbeat"}',
      'data: {"type":"session","payload":{}}',
      'data: {"type":"conversation_state","payload":{}}',
      'data: {"type":"thinking","message":"Real event"}',
    ]);
    expect(events).toEqual([{ type: 'thinking', message: 'Real event' }]);
  });

  it('heartbeat events are silently skipped between results', async () => {
    const events = await collectEvents([
      'data: {"type":"result","payload":{"connection_id":"c1","crawled_profile_id":"cp1","full_name":"Alice"}}',
      'data: {"type":"heartbeat"}',
      'data: {"type":"result","payload":{"connection_id":"c2","crawled_profile_id":"cp2","full_name":"Bob"}}',
      'data: {"type":"done","payload":{"total":2}}',
    ]);
    const heartbeats = events.filter(e => e.type === 'heartbeat' as string);
    expect(heartbeats).toHaveLength(0);
    const results = events.filter(e => e.type === 'result');
    expect(results).toHaveLength(2);
    expect((results[0] as { type: 'result'; data: { rank: number; name: string } }).data.rank).toBe(1);
    expect((results[1] as { type: 'result'; data: { rank: number; name: string } }).data.rank).toBe(2);
  });

  it('stream resilience with interleaved heartbeats', async () => {
    const events = await collectEvents([
      'data: {"type":"heartbeat"}',
      'data: {"type":"result","payload":{"connection_id":"c1","crawled_profile_id":"cp1","full_name":"Alice"}}',
      'data: {"type":"heartbeat"}',
      'data: {"type":"result","payload":{"connection_id":"c2","crawled_profile_id":"cp2","full_name":"Bob"}}',
      'data: {"type":"heartbeat"}',
      'data: {"type":"done","payload":{"total":2}}',
    ]);
    expect(events.filter(e => e.type === 'result')).toHaveLength(2);
    expect(events.filter(e => e.type === 'done')).toHaveLength(1);
    expect(events).toHaveLength(3); // 2 results + 1 done, no heartbeats
  });

  it('long-running stream with only heartbeats then results', async () => {
    const events = await collectEvents([
      'data: {"type":"heartbeat"}',
      'data: {"type":"heartbeat"}',
      'data: {"type":"heartbeat"}',
      'data: {"type":"thinking","message":"Still working..."}',
      'data: {"type":"result","payload":{"connection_id":"c1","crawled_profile_id":"cp1","full_name":"Alice"}}',
      'data: {"type":"done","payload":{"total":1}}',
    ]);
    expect(events).toEqual([
      { type: 'thinking', message: 'Still working...' },
      { type: 'result', data: expect.objectContaining({ rank: 1, name: 'Alice' }) },
      { type: 'done', data: expect.objectContaining({ totalResults: 1 }) },
    ]);
  });

  it('skips malformed JSON lines', async () => {
    const events = await collectEvents([
      'data: {not json at all',
      'data: {"type":"thinking","message":"OK"}',
    ]);
    expect(events).toEqual([{ type: 'thinking', message: 'OK' }]);
  });

  it('skips [DONE] marker', async () => {
    const events = await collectEvents([
      'data: {"type":"thinking","message":"Start"}',
      'data: [DONE]',
    ]);
    expect(events).toEqual([{ type: 'thinking', message: 'Start' }]);
  });

  it('network error → emits error event (no throw)', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('fetch failed'));
    const events: BestHopEvent[] = [];
    const params: BestHopParams = {
      targetName: 'Jane',
      targetUrl: 'https://www.linkedin.com/in/jane',
      mutualUrls: [],
    };

    await streamBestHop(params, new AbortController().signal, e => events.push(e));

    expect(events).toEqual([{ type: 'error', data: { message: 'Backend is unreachable' } }]);
  });

  it('non-2xx → emits error with status', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      text: () => Promise.resolve('server error'),
    } as unknown as Response);
    const events: BestHopEvent[] = [];
    const params: BestHopParams = {
      targetName: 'Jane',
      targetUrl: 'https://www.linkedin.com/in/jane',
      mutualUrls: [],
    };

    await streamBestHop(params, new AbortController().signal, e => events.push(e));

    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('error');
    expect((events[0] as { type: 'error'; data: { message: string } }).data.message).toContain('500');
  });

  it('AbortSignal → silently returns', async () => {
    const abortError = new DOMException('Aborted', 'AbortError');
    mockFetch.mockRejectedValueOnce(abortError);
    const events: BestHopEvent[] = [];
    const controller = new AbortController();
    controller.abort();
    const params: BestHopParams = {
      targetName: 'Jane',
      targetUrl: 'https://www.linkedin.com/in/jane',
      mutualUrls: [],
    };

    await streamBestHop(params, controller.signal, e => events.push(e));

    expect(events).toHaveLength(0);
  });
});
