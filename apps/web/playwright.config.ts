import { defineConfig, devices } from '@playwright/test';

const webPort = process.env.WEB_PORT || '3000';
const apiBase = process.env.API_BASE_URL || 'http://127.0.0.1:8000';

export default defineConfig({
  testDir: './e2e',
  timeout: 180_000,
  expect: { timeout: 60_000 },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  metadata: { apiBase },
});
