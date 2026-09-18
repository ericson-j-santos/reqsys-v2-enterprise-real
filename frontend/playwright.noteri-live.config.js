const { defineConfig, devices } = require('@playwright/test')

module.exports = defineConfig({
  testDir: './tests/e2e',
  testMatch: ['noteri-task-console-live.spec.js'],
  timeout: 60_000,
  retries: 0,
  workers: 1,
  outputDir: 'test-results/noteri-task-console-live',
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5173',
    cwd: '.',
    url: 'http://127.0.0.1:5173/login',
    reuseExistingServer: true,
    timeout: 120_000,
  },
  projects: [
    {
      name: 'noteri-local-chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
