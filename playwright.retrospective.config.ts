import { defineConfig } from '@playwright/test';

if (!process.env.E2E_BASE_URL || !/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(process.env.E2E_BASE_URL)) {
  throw new Error('Destino local explícito requerido');
}
export default defineConfig({ testDir: './tests/e2e', testMatch: ['retrospective.spec.ts'], workers: 1,
  timeout: 60000, outputDir: '.local/retro-playwright-results',
  reporter: [['json', { outputFile: 'tests/evidence/retro-playwright.json' }]],
  use: { baseURL: process.env.E2E_BASE_URL, locale: 'es-PE', trace: 'off', screenshot: 'off', video: 'off' } });
