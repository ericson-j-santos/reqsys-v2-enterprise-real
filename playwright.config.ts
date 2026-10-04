import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './frontend/tests/e2e',
  timeout: 60000,
  retries: 1,
  fullyParallel: false,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    headless: true,
    screenshot: 'only-on-failure',
    video: 'off',
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5173',
    cwd: './frontend',
    url: 'http://127.0.0.1:5173/login',
    reuseExistingServer: true,
    timeout: 120000,
  },
  projects: [
    {
      name: 'frontend-canonico',
      use: { ...devices['Desktop Chrome'] },
      testMatch: [
        '**/login-accessibility.spec.js',
        '**/responsividade.spec.js',
        '**/estatistica-detalhe.spec.js',
      ],
    },
  ],
})
