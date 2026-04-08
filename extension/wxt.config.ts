// SPDX-License-Identifier: Apache-2.0
import { defineConfig } from 'wxt';

export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  manifest: {
    name: 'LinkedOut',
    description: 'LinkedIn profile intelligence powered by LinkedOut',
    permissions: ['sidePanel', 'storage', 'activeTab', 'tabs'],
    host_permissions: ['https://www.linkedin.com/*'],
  },
});
