// SPDX-License-Identifier: Apache-2.0
import { defineConfig } from 'vitest/config';
import { resolve } from 'path';

export default defineConfig({
  resolve: {
    alias: {
      // Point wxt/browser at the WXT fake-browser shim so browser.storage etc.
      // are available in Vitest without a real extension environment.
      'wxt/browser': resolve('./node_modules/wxt/dist/virtual/mock-browser.mjs'),
    },
  },
  test: {
    include: ['lib/**/__tests__/**/*.test.ts'],
    setupFiles: ['./lib/test-setup.ts'],
  },
});
