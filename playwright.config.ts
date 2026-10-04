import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'access.spec.ts',
  workers: 1,
  outputDir: '.local/playwright-results',
  reporter: [['line'], ['json', { outputFile: process.env.E2E_REPORT_FILE ?? 'tests/evidence/s2-1-playwright.json' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:15174',
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
});
