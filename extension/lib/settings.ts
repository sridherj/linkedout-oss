// SPDX-License-Identifier: Apache-2.0
/**
 * Extension settings — delegates to the unified config module.
 * Kept for backward compatibility with existing consumers (side panel, background).
 */

import { getConfig, saveConfig, onConfigChange, type EnrichmentMode } from './config';

// Re-export the type so consumers don't need to change imports
export type { EnrichmentMode };

/** Get the current enrichment mode from unified config. */
export async function getEnrichmentMode(): Promise<EnrichmentMode> {
  const config = await getConfig();
  return config.enrichmentMode;
}

/** Persist the enrichment mode via unified config. */
export async function setEnrichmentMode(mode: EnrichmentMode): Promise<void> {
  await saveConfig({ enrichmentMode: mode });
}

/** Subscribe to enrichment mode changes. Returns an unsubscribe function. */
export function onEnrichmentModeChange(
  callback: (mode: EnrichmentMode) => void,
): () => void {
  let lastMode: EnrichmentMode | null = null;
  return onConfigChange((config) => {
    if (config.enrichmentMode !== lastMode) {
      lastMode = config.enrichmentMode;
      callback(config.enrichmentMode);
    }
  });
}
