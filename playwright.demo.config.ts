import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e', testMatch: ['demo-manual.spec.ts'], workers: 1,
  timeout: 120000, outputDir: '.local/demo-playwright',
  reporter: [['json', { outputFile: process.env.DEMO_REPORT ?? 'tests/evidence/mejoras-01-e2e.json' }]],
  use: { channel: process.env.DEMO_BROWSER_CHANNEL ?? 'chrome', locale: 'es-PE', baseURL: process.env.DEMO_BASE, trace: 'off', screenshot: 'off', video: 'off' },
});
