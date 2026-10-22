import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E Configuration for Bio-Chain
 * Configured with workers: 1 to ensure sequential execution on local SQLite database.
 */
export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.ts',
  timeout: 90 * 1000,
  expect: {
    timeout: 15 * 1000,
  },
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: process.env.BIOCHAIN_URL || 'http://127.0.0.1:8000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
