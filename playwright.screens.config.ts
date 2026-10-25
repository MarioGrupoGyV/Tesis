import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e', testMatch: ['screens-b9.spec.ts'], workers: 1,
  timeout: 300000, outputDir: '.local/screens-playwright',
  reporter: [['list']],
  use: { channel: process.env.SCREENS_BROWSER_CHANNEL ?? 'chrome', locale: 'es-PE', trace: 'off', screenshot: 'off', video: 'off' },
});
