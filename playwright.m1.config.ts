import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e', testMatch: ['m1.spec.ts'], workers: 1,
  timeout: 90000, outputDir: '.local/m1-playwright',
  reporter: [['json', { outputFile: process.env.M1_REPORT ?? 'tests/evidence/m1-browser-first.json' }]],
  use: { locale: 'es-PE', baseURL: process.env.M1_BASE, trace: 'off', screenshot: 'off', video: 'off' },
});
