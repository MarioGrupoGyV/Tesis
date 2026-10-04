import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 's1.spec.ts',
  workers: 1,
  outputDir: '.local/playwright-results',
  reporter: [['line'], ['json', { outputFile: 'tests/evidence/s1-playwright.json' }]],
  use: {
    baseURL: process.env.S1_BASE_URL ?? 'http://localhost:15173',
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
});
