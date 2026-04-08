// SPDX-License-Identifier: Apache-2.0
/**
 * ISOLATED world content script — pure relay, zero business logic.
 * Bridges CustomEvents from MAIN world ↔ chrome.runtime messages to service worker.
 */

import { browser } from 'wxt/browser';
import type { ExtensionMessage } from '../lib/messages';

// Custom event names matching voyager.content.ts
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
  runAt: 'document_idle',
  // world defaults to ISOLATED in WXT

  main() {
    // ── MAIN → bridge → SW: forward CustomEvents as chrome.runtime messages ──
    function forwardToSW(eventName: string) {
      document.addEventListener(eventName, ((e: CustomEvent<ExtensionMessage>) => {
        browser.runtime.sendMessage(e.detail).catch(() => {
          // SW not available (extension context invalidated) — silently ignore
        });
      }) as EventListener);
    }

    forwardToSW(EVT_URL_CHANGED);
    forwardToSW(EVT_VOYAGER_DATA_READY);
    forwardToSW(EVT_VOYAGER_DATA_ERROR);
    forwardToSW(EVT_MUTUAL_PROGRESS);
    forwardToSW(EVT_MUTUAL_READY);
    forwardToSW(EVT_EXTRACTION_SPEED_CHANGED);

    // ── SW → bridge → MAIN: forward chrome.runtime messages as CustomEvents ──
    browser.runtime.onMessage.addListener((message: ExtensionMessage) => {
      switch (message.type) {
        case 'RETRY_FETCH':
          document.dispatchEvent(
            new CustomEvent(EVT_RETRY_FETCH, { detail: message }),
          );
          break;
        case 'EXTRACT_MUTUAL_CONNECTIONS':
          document.dispatchEvent(
            new CustomEvent(EVT_EXTRACT_MUTUAL, { detail: message }),
          );
          break;
        case 'SET_EXTRACTION_SPEED':
          document.dispatchEvent(
            new CustomEvent(EVT_SET_EXTRACTION_SPEED, { detail: message }),
          );
          break;
      }
    });
  },
});
