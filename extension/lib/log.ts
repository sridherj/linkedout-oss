// SPDX-License-Identifier: Apache-2.0
/** Local activity log backed by browser.storage.local. */

import { browser } from 'wxt/browser';
import { getConfigSync } from './config';

const STORAGE_KEY = 'activityLog';

export type LogAction =
  | 'fetched'
  | 'saved'
  | 'updated'
  | 'skipped'
  | 'rate_limited'
  | 'error'
  | 'best_hop'
  | 'api_call';

export interface LogEntry {
  timestamp: string;
  action: LogAction;
  profileName?: string;
  profileHeadline?: string;
  linkedinUrl?: string;
  reason?: string;
  /** Backend API call fields (action='api_call') */
  method?: string;
  path?: string;
  statusCode?: number;
  durationMs?: number;
  /** Rate limit fields (action='rate_limited') */
  limitName?: string;
  retryAfterMs?: number;
  currentCount?: number;
  limitMax?: number;
}

async function getEntries(): Promise<LogEntry[]> {
  const result = await browser.storage.local.get(STORAGE_KEY);
  return (result[STORAGE_KEY] as LogEntry[]) ?? [];
}

/**
 * Upsert a log entry (most recent first), capped at config.maxLogEntries.
 * If an entry with the same linkedinUrl exists, it is replaced and moved to the top.
 * @param entry - The log entry to record.
 */
export async function appendLog(entry: LogEntry): Promise<void> {
  const entries = await getEntries();
  // Remove existing entry for same profile (upsert)
  if (entry.linkedinUrl) {
    const idx = entries.findIndex((e) => e.linkedinUrl === entry.linkedinUrl);
    if (idx !== -1) entries.splice(idx, 1);
  }
  entries.unshift(entry);
  const maxEntries = getConfigSync().maxLogEntries;
  if (entries.length > maxEntries) entries.length = maxEntries;
  await browser.storage.local.set({ [STORAGE_KEY]: entries });
}

/**
 * Get the most recent log entries.
 * @param limit - Optional max entries to return.
 */
export async function getLogs(limit?: number): Promise<LogEntry[]> {
  const entries = await getEntries();
  return limit ? entries.slice(0, limit) : entries;
}

/** Clear all log entries. */
export async function clearLogs(): Promise<void> {
  await browser.storage.local.set({ [STORAGE_KEY]: [] });
}

/**
 * Log a backend API call with method, path, status, and duration.
 * @param method - HTTP method (GET, POST, etc.).
 * @param path - API endpoint path.
 * @param statusCode - HTTP response status code.
 * @param durationMs - Request duration in milliseconds.
 * @param error - Optional error message if the call failed.
 */
export async function logApiCall(
  method: string,
  path: string,
  statusCode: number,
  durationMs: number,
  error?: string,
): Promise<void> {
  await appendLog({
    timestamp: new Date().toISOString(),
    action: 'api_call',
    method,
    path,
    statusCode,
    durationMs,
    reason: error,
  });
}

/**
 * Log a rate limit event with details about the limit hit.
 * @param opts - Rate limit details.
 */
export async function logRateLimit(opts: {
  limitName: string;
  retryAfterMs?: number;
  currentCount?: number;
  limitMax?: number;
  linkedinUrl?: string;
}): Promise<void> {
  await appendLog({
    timestamp: new Date().toISOString(),
    action: 'rate_limited',
    linkedinUrl: opts.linkedinUrl,
    limitName: opts.limitName,
    retryAfterMs: opts.retryAfterMs,
    currentCount: opts.currentCount,
    limitMax: opts.limitMax,
    reason: opts.retryAfterMs
      ? `${opts.limitName} — retry after ${opts.retryAfterMs}ms`
      : opts.limitName,
  });
}
