// SPDX-License-Identifier: Apache-2.0
/**
 * Runtime configuration module.
 * Reads from browser.storage.local with fallbacks to build-time env vars and hardcoded defaults.
 * Config is cached at startup — call initConfig() once in the background script.
 *
 * The options page writes to browser.storage.local via saveConfig().
 * Storage change listeners invalidate the cache so getConfigSync() always reflects the latest values.
 */

import { browser, type Browser } from 'wxt/browser';

export type EnrichmentMode = 'manual' | 'auto';

export interface ExtensionConfig {
  // User-configurable (options page)
  backendUrl: string;
  stalenessDays: number;
  hourlyLimit: number;
  dailyLimit: number;
  tenantId: string;
  buId: string;
  userId: string;
  enrichmentMode: EnrichmentMode;
  // Internal tuning (not on options page)
  minFetchDelayMs: number;
  maxFetchDelayMs: number;
  maxLogEntries: number;
  mutualMaxPages: number;
  urlDebounceMs: number;
  recentActivityLimit: number;
  mutualFirstPageDelayBaseMs: number;
  mutualFirstPageDelayRangeMs: number;
}

/** Keys exposed on the options page. */
export type ConfigurableKeys = 'backendUrl' | 'stalenessDays' | 'hourlyLimit' | 'dailyLimit'
  | 'tenantId' | 'buId' | 'userId' | 'enrichmentMode';

const STORAGE_KEY = 'linkedout_config';

const DEFAULTS: ExtensionConfig = {
  backendUrl: import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001',
  stalenessDays: 30,
  hourlyLimit: 30,
  dailyLimit: 150,
  tenantId: 'tenant_sys_001',
  buId: 'bu_sys_001',
  userId: 'usr_sys_001',
  enrichmentMode: 'manual',
  minFetchDelayMs: 2000,
  maxFetchDelayMs: 5000,
  maxLogEntries: 200,
  mutualMaxPages: 10,
  urlDebounceMs: 500,
  recentActivityLimit: 20,
  mutualFirstPageDelayBaseMs: 1000,
  mutualFirstPageDelayRangeMs: 1500,
};

// Cached config — loaded once at startup, invalidated on storage changes
let _cachedConfig: ExtensionConfig | null = null;

export async function getConfig(): Promise<ExtensionConfig> {
  if (_cachedConfig) return _cachedConfig;

  const stored = await browser.storage.local.get(STORAGE_KEY);
  _cachedConfig = { ...DEFAULTS, ...(stored[STORAGE_KEY] || {}) };
  return _cachedConfig;
}

/** Synchronous access after initial load (returns defaults if not yet loaded). */
export function getConfigSync(): ExtensionConfig {
  return _cachedConfig || DEFAULTS;
}

/** Call once at extension startup (e.g., in background script). */
export async function initConfig(): Promise<ExtensionConfig> {
  _cachedConfig = null; // force reload
  const config = await getConfig();

  // Migrate legacy enrichmentMode key (pre-options-page) into unified config
  const legacy = await browser.storage.local.get('enrichmentMode');
  if (legacy['enrichmentMode']) {
    const stored = await browser.storage.local.get(STORAGE_KEY);
    const storedConfig = (stored[STORAGE_KEY] || {}) as Partial<ExtensionConfig>;
    if (!storedConfig.enrichmentMode) {
      await saveConfig({ enrichmentMode: legacy['enrichmentMode'] as EnrichmentMode });
      await browser.storage.local.remove('enrichmentMode');
    }
  }

  return config;
}

/** Save partial config to storage. Merges with existing stored values. */
export async function saveConfig(partial: Partial<ExtensionConfig>): Promise<void> {
  const stored = await browser.storage.local.get(STORAGE_KEY);
  const current = stored[STORAGE_KEY] || {};
  const merged = { ...current, ...partial };
  await browser.storage.local.set({ [STORAGE_KEY]: merged });
  // Cache is invalidated by the storage change listener below
}

/** Subscribe to config changes. Returns an unsubscribe function. */
export function onConfigChange(callback: (config: ExtensionConfig) => void): () => void {
  const listener = (
    changes: Record<string, Browser.storage.StorageChange>,
    area: string,
  ) => {
    if (area === 'local' && changes[STORAGE_KEY]) {
      _cachedConfig = { ...DEFAULTS, ...(changes[STORAGE_KEY].newValue || {}) };
      callback(_cachedConfig);
    }
  };
  browser.storage.onChanged.addListener(listener);
  return () => browser.storage.onChanged.removeListener(listener);
}

// Auto-invalidate cache on storage changes (covers options page saves, other contexts)
if (typeof browser !== 'undefined' && browser.storage?.onChanged) {
  browser.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes[STORAGE_KEY]) {
      _cachedConfig = { ...DEFAULTS, ...(changes[STORAGE_KEY].newValue || {}) };
    }
  });
}
