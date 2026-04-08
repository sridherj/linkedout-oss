// SPDX-License-Identifier: Apache-2.0
// Vitest global setup: stub WebExtension browser APIs with a fake implementation.
import { vi, beforeEach } from 'vitest';
import { fakeBrowser } from 'wxt/testing';

beforeEach(() => {
  fakeBrowser.reset();
});

vi.stubGlobal('chrome', fakeBrowser);
vi.stubGlobal('browser', fakeBrowser);
