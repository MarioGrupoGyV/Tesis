import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e', testMatch: ['real-cycle.spec.ts'], workers: 1,
  timeout: 240000, outputDir: '.local/real-playwright',
  reporter: [['json', { outputFile: process.env.DEMO_REPORT ?? 'tests/evidence/mejoras-03b2-e2e.json' }]],
  use: { channel: process.env.DEMO_BROWSER_CHANNEL ?? 'chrome', locale: 'es-PE', baseURL: process.env.DEMO_BASE, trace: 'off', screenshot: 'off', video: 'off' },
});
