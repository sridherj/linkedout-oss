// SPDX-License-Identifier: Apache-2.0
/** Sliding window rate limiter backed by browser.storage.local. */

import { browser } from 'wxt/browser';
import { getConfigSync } from './config';
import { devLog } from './dev-log';

const STORAGE_KEY = 'rateLimitTimestamps';

async function getTimestamps(): Promise<string[]> {
  const result = await browser.storage.local.get(STORAGE_KEY);
  return (result[STORAGE_KEY] as string[]) ?? [];
}

async function setTimestamps(timestamps: string[]): Promise<void> {
  await browser.storage.local.set({ [STORAGE_KEY]: timestamps });
}

function countSince(timestamps: string[], since: Date): number {
  const threshold = since.getTime();
  return timestamps.filter((ts) => new Date(ts).getTime() >= threshold).length;
}

function pruneOlderThan(timestamps: string[], since: Date): string[] {
  const threshold = since.getTime();
  return timestamps.filter((ts) => new Date(ts).getTime() >= threshold);
}

/**
 * Check if we can proceed without exceeding hourly or daily limits.
 * @returns true if both hourly and daily limits have remaining capacity.
 */
export async function canProceed(): Promise<boolean> {
  const now = new Date();
  const timestamps = await getTimestamps();

  const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
  const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);

  const hourlyUsed = countSince(timestamps, oneHourAgo);
  const dailyUsed = countSince(timestamps, oneDayAgo);

  const config = getConfigSync();

  if (hourlyUsed >= config.hourlyLimit) {
    const retryMs = 60 * 60 * 1000; // wait up to 1 hour for window to slide
    devLog('warn', 'rate-limiter', 'Hourly limit reached', {
      limit: 'hourly',
      current: hourlyUsed,
      max: config.hourlyLimit,
      retryAfterMs: retryMs,
      retryGuidance: 'Wait for oldest request to age out of the 1-hour window',
    });
    return false;
  }

  if (dailyUsed >= config.dailyLimit) {
    const retryMs = 24 * 60 * 60 * 1000; // wait up to 24 hours
    devLog('warn', 'rate-limiter', 'Daily limit reached', {
      limit: 'daily',
      current: dailyUsed,
      max: config.dailyLimit,
      retryAfterMs: retryMs,
      retryGuidance: 'Wait for oldest request to age out of the 24-hour window',
    });
    return false;
  }

  return true;
}

/** Record a fetch timestamp and prune entries older than 24h. */
export async function record(): Promise<void> {
  const now = new Date();
  const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);

  let timestamps = await getTimestamps();
  timestamps = pruneOlderThan(timestamps, oneDayAgo);
  timestamps.push(now.toISOString());

  await setTimestamps(timestamps);
}

/**
 * Get current rate limit status for UI display.
 * @returns Hourly and daily usage counts with their limits.
 */
export async function getStatus(): Promise<{
  hourly: { used: number; limit: number };
  daily: { used: number; limit: number };
}> {
  const now = new Date();
  const timestamps = await getTimestamps();

  const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
  const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);

  const config = getConfigSync();
  return {
    hourly: { used: countSince(timestamps, oneHourAgo), limit: config.hourlyLimit },
    daily: { used: countSince(timestamps, oneDayAgo), limit: config.dailyLimit },
  };
}
