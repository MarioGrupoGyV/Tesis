import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  // S6 tiene destinos nuevos explícitos. No cargar los guards de los runners
  // históricos ni reutilizar su URL predeterminada para otra instalación.
  testMatch: process.env.E2E_PHASE?.startsWith('s6-') ? ['s6.spec.ts'] : ['access.spec.ts', 's5.spec.ts'],
  workers: 1,
  outputDir: '.local/playwright-results',
  reporter: process.env.E2E_PHASE?.startsWith('s6-') ? './tests/e2e/s6-reporter.ts' : './tests/e2e/review-reporter.ts',
  use: {
    locale: 'es-PE',
    baseURL: process.env.E2E_PHASE?.startsWith('s6-') ? process.env.E2E_BASE_URL : process.env.E2E_BASE_URL ?? 'http://localhost:15174',
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
});
