import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e', testMatch: ['estudio-real-b10.spec.ts'], workers: 1,
  timeout: 240000, outputDir: '.local/realset-playwright',
  reporter: [['list']],
  use: { channel: process.env.REALSET_BROWSER_CHANNEL ?? 'chrome', locale: 'es-PE', trace: 'off', screenshot: 'off', video: 'off' },
});
