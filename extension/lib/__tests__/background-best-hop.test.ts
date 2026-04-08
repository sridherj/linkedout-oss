// SPDX-License-Identifier: Apache-2.0
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { BestHopEvent } from '../backend/search';

// ── State shared between hoisted mocks and test code via vi.hoisted ──
const state = vi.hoisted(() => {
  const s = {
    sentMessages: [] as unknown[],
    messageListener: null as ((msg: unknown) => void) | null,
    innerListener: null as ((msg: unknown) => void) | null,
    streamBestHop: vi.fn(),
  };

  // defineBackground must be available before background.ts is imported
  (globalThis as any).defineBackground = (fn: () => void) => { fn(); };

  return s;
});

vi.mock('wxt/browser', () => ({
  browser: {
    sidePanel: { setPanelBehavior: vi.fn() },
    runtime: {
      sendMessage: vi.fn(async (msg: unknown) => { state.sentMessages.push(msg); }),
      onMessage: {
        addListener: vi.fn((handler: (msg: unknown) => void) => {
          if (!state.messageListener) {
            state.messageListener = handler;
          } else {
            state.innerListener = handler;
          }
        }),
        removeListener: vi.fn(),
      },
      onConnect: { addListener: vi.fn() },
    },
    tabs: {
      query: vi.fn(async () => [{ id: 1, url: 'https://www.linkedin.com/in/test' }]),
      sendMessage: vi.fn(async () => {}),
      onUpdated: { addListener: vi.fn() },
    },
  },
}));

vi.mock('../backend/search', () => ({
  streamBestHop: (...args: unknown[]) => state.streamBestHop(...args),
}));

vi.mock('../backend/client', () => ({
  checkFreshness: vi.fn(async () => ({ exists: false })),
  createProfile: vi.fn(async () => 'new_id'),
  updateProfile: vi.fn(),
  enrichProfile: vi.fn(),
  BackendUnreachable: class extends Error {},
  BackendError: class extends Error { status = 0; },
}));
vi.mock('../../lib/voyager/parser', () => ({ parseVoyagerProfile: vi.fn() }));
vi.mock('../../lib/profile/mapper', () => ({ toCrawledProfilePayload: vi.fn(), toEnrichPayload: vi.fn() }));
vi.mock('../../lib/profile/url', () => ({ isLinkedInProfilePage: vi.fn(() => false), extractProfileId: vi.fn() }));
vi.mock('../../lib/rate-limiter', () => ({
  canProceed: vi.fn(async () => true), record: vi.fn(),
  getStatus: vi.fn(async () => ({ hourly: { used: 0, limit: 100 }, daily: { used: 0, limit: 500 } })),
}));
vi.mock('../../lib/settings', () => ({ getEnrichmentMode: vi.fn(async () => 'manual'), onEnrichmentModeChange: vi.fn() }));
vi.mock('../../lib/log', () => ({ appendLog: vi.fn(async () => {}) }));
vi.mock('../../lib/config', () => ({
  initConfig: vi.fn(async () => ({ backendUrl: 'http://localhost:8001', stalenessDays: 7, hourlyLimit: 30, dailyLimit: 150 })),
  getConfigSync: vi.fn(() => ({ backendUrl: 'http://localhost:8001', stalenessDays: 7, hourlyLimit: 30, dailyLimit: 150 })),
}));

// Import triggers defineBackground, registering the message listener
import '../../entrypoints/background';

function findBestHopMsg() {
  return {
    type: 'FIND_BEST_HOP' as const,
    entityUrn: 'urn:li:fsd_profile:abc123',
    linkedinUrl: 'https://www.linkedin.com/in/test',
    profileName: 'Test User',
  };
}

async function triggerBestHopWithMutuals() {
  state.messageListener!(findBestHopMsg());
  await new Promise(r => setTimeout(r, 10));

  if (state.innerListener) {
    state.innerListener({
      type: 'MUTUAL_CONNECTIONS_READY',
      urls: ['https://www.linkedin.com/in/alice'],
      pagesScraped: 1,
      stopped: false,
    });
  }
  await new Promise(r => setTimeout(r, 50));
}

describe('background Best Hop orchestration', () => {
  beforeEach(() => {
    state.sentMessages.length = 0;
    state.innerListener = null;
    state.streamBestHop.mockReset();
  });

  it('handleFindBestHop broadcasts BEST_HOP_THINKING to side panel', async () => {
    expect(state.messageListener).toBeTruthy();

    state.streamBestHop.mockImplementation(async (_p: unknown, _s: AbortSignal, onEvent: (e: BestHopEvent) => void) => {
      onEvent({ type: 'thinking', message: 'Analyzing connections...' });
    });

    await triggerBestHopWithMutuals();

    const thinkingMsgs = state.sentMessages.filter((m: any) => m.type === 'BEST_HOP_THINKING');
    expect(thinkingMsgs.length).toBeGreaterThanOrEqual(1);
    expect((thinkingMsgs[0] as any).message).toBe('Analyzing connections...');
  });

  it('handleFindBestHop broadcasts BEST_HOP_RESULT for each result', async () => {
    state.streamBestHop.mockImplementation(async (_p: unknown, _s: AbortSignal, onEvent: (e: BestHopEvent) => void) => {
      onEvent({
        type: 'result',
        data: { rank: 1, connectionId: 'c1', crawledProfileId: 'cp1', name: 'Alice', role: 'Engineer', affinityScore: 0.9, reasoning: 'Strong', linkedinUrl: 'https://www.linkedin.com/in/alice' },
      });
      onEvent({
        type: 'result',
        data: { rank: 2, connectionId: 'c2', crawledProfileId: 'cp2', name: 'Bob', role: 'PM', affinityScore: 0.7, reasoning: 'Good', linkedinUrl: 'https://www.linkedin.com/in/bob' },
      });
    });

    await triggerBestHopWithMutuals();

    const resultMsgs = state.sentMessages.filter((m: any) => m.type === 'BEST_HOP_RESULT');
    expect(resultMsgs).toHaveLength(2);
    expect((resultMsgs[0] as any).name).toBe('Alice');
    expect((resultMsgs[1] as any).name).toBe('Bob');
  });

  it('handleFindBestHop broadcasts BEST_HOP_COMPLETE on done', async () => {
    state.streamBestHop.mockImplementation(async (_p: unknown, _s: AbortSignal, onEvent: (e: BestHopEvent) => void) => {
      onEvent({ type: 'done', data: { totalResults: 3, matched: 10, unmatched: 2 } });
    });

    await triggerBestHopWithMutuals();

    const doneMsgs = state.sentMessages.filter((m: any) => m.type === 'BEST_HOP_COMPLETE');
    expect(doneMsgs.length).toBeGreaterThanOrEqual(1);
    expect((doneMsgs[0] as any).totalResults).toBe(3);
    expect((doneMsgs[0] as any).matched).toBe(10);
    expect((doneMsgs[0] as any).unmatched).toBe(2);
  });

  it('handleFindBestHop broadcasts BEST_HOP_ERROR on error', async () => {
    state.streamBestHop.mockImplementation(async (_p: unknown, _s: AbortSignal, onEvent: (e: BestHopEvent) => void) => {
      onEvent({ type: 'error', data: { message: 'Search backend timeout' } });
    });

    await triggerBestHopWithMutuals();

    const errorMsgs = state.sentMessages.filter((m: any) => m.type === 'BEST_HOP_ERROR');
    expect(errorMsgs.length).toBeGreaterThanOrEqual(1);
    expect((errorMsgs[0] as any).message).toBe('Search backend timeout');
    expect((errorMsgs[0] as any).phase).toBe('search');
  });

  it('handleCancelBestHop aborts stream and sends completion', async () => {
    let capturedSignal: AbortSignal | null = null;

    state.streamBestHop.mockImplementation(async (_p: unknown, signal: AbortSignal, _onEvent: (e: BestHopEvent) => void) => {
      capturedSignal = signal;
      await new Promise<void>((resolve) => {
        signal.addEventListener('abort', () => resolve(), { once: true });
      });
    });

    state.messageListener!(findBestHopMsg());
    await new Promise(r => setTimeout(r, 10));
    if (state.innerListener) {
      state.innerListener({
        type: 'MUTUAL_CONNECTIONS_READY',
        urls: ['https://www.linkedin.com/in/alice'],
        pagesScraped: 1,
        stopped: false,
      });
    }
    await new Promise(r => setTimeout(r, 20));

    state.sentMessages.length = 0;
    state.messageListener!({ type: 'CANCEL_BEST_HOP' });
    await new Promise(r => setTimeout(r, 20));

    const completeMsgs = state.sentMessages.filter((m: any) => m.type === 'BEST_HOP_COMPLETE');
    expect(completeMsgs).toHaveLength(1);
    expect((completeMsgs[0] as any).totalResults).toBe(0);
    expect(capturedSignal!.aborted).toBe(true);
  });

  it('concurrent Best Hop requests — second request aborts the first', async () => {
    let firstSignal: AbortSignal | null = null;

    state.streamBestHop
      .mockImplementationOnce(async (_p: unknown, signal: AbortSignal, _onEvent: (e: BestHopEvent) => void) => {
        firstSignal = signal;
        await new Promise<void>((resolve) => {
          signal.addEventListener('abort', () => resolve(), { once: true });
        });
      })
      .mockImplementationOnce(async (_p: unknown, _signal: AbortSignal, onEvent: (e: BestHopEvent) => void) => {
        onEvent({ type: 'done', data: { totalResults: 1, matched: 5, unmatched: 0 } });
      });

    // First request
    state.messageListener!(findBestHopMsg());
    await new Promise(r => setTimeout(r, 10));
    if (state.innerListener) {
      state.innerListener({
        type: 'MUTUAL_CONNECTIONS_READY',
        urls: ['https://www.linkedin.com/in/alice'],
        pagesScraped: 1,
        stopped: false,
      });
    }
    await new Promise(r => setTimeout(r, 20));

    // Second request (should abort first)
    state.innerListener = null;
    state.messageListener!(findBestHopMsg());
    await new Promise(r => setTimeout(r, 10));
    if (state.innerListener) {
      state.innerListener({
        type: 'MUTUAL_CONNECTIONS_READY',
        urls: ['https://www.linkedin.com/in/bob'],
        pagesScraped: 1,
        stopped: false,
      });
    }
    await new Promise(r => setTimeout(r, 50));

    expect(firstSignal!.aborted).toBe(true);
  });
});
