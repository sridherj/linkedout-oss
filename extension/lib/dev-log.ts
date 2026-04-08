// SPDX-License-Identifier: Apache-2.0
/**
 * Structured dev logging — zero-cost in production builds.
 *
 * Outputs only when:
 *   1. import.meta.env.DEV is true (development mode), OR
 *   2. LINKEDOUT_DEBUG=true in browser.storage.local
 *
 * Toggle at runtime via devtools console:
 *   browser.storage.local.set({ LINKEDOUT_DEBUG: true })
 */

import { browser } from 'wxt/browser';

export type DevLogComponent =
  | 'background'
  | 'voyager'
  | 'backend-client'
  | 'side-panel'
  | 'options'
  | 'rate-limiter';

let debugEnabled: boolean | null = null;

async function isDebugEnabled(): Promise<boolean> {
  if (import.meta.env.DEV) return true;
  if (debugEnabled !== null) return debugEnabled;
  try {
    const result = await browser.storage.local.get('LINKEDOUT_DEBUG');
    debugEnabled = result.LINKEDOUT_DEBUG === true || result.LINKEDOUT_DEBUG === 'true';
  } catch {
    debugEnabled = false;
  }
  return debugEnabled;
}

/**
 * Structured dev-only logging utility.
 * Format: [LinkedOut][{component}] {level}: {message}
 *
 * Zero-cost in production: the async check short-circuits immediately
 * when import.meta.env.DEV is false and debug flag is cached.
 */
export async function devLog(
  level: 'debug' | 'info' | 'warn' | 'error',
  component: DevLogComponent,
  message: string,
  data?: unknown,
): Promise<void> {
  if (!(await isDebugEnabled())) return;
  const prefix = `[LinkedOut][${component}] ${level}:`;
  if (data !== undefined) {
    console[level](prefix, message, data);
  } else {
    console[level](prefix, message);
  }
}

/** Reset the cached debug flag (e.g., after storage changes). */
export function resetDebugCache(): void {
  debugEnabled = null;
}
