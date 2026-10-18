import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e', testMatch: ['real-tesis.spec.ts'], workers: 1, timeout: 240000, outputDir: '.local/real-tesis-playwright',
  reporter: [['json', { outputFile: 'tests/evidence/mejoras-05-e2e.json' }]],
  use: { channel: process.env.DEMO_BROWSER_CHANNEL ?? 'chrome', locale: 'es-PE', baseURL: process.env.REAL_BASE, trace: 'off', screenshot: 'off', video: 'off' },
});
