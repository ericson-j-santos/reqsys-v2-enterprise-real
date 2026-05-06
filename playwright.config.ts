import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  retries: 1,
  fullyParallel: false,
  use: {
    headless: true,
    screenshot: 'only-on-failure',
    video: 'off',
  },
  webServer: [
    {
      command: 'npm run dev',
      cwd: './frontend-vuetify',
      url: 'http://localhost:5174/login',
      reuseExistingServer: true,
      timeout: 120000,
    },
    {
      command: 'npx ng serve --host 0.0.0.0 --port 4200 --proxy-config proxy.conf.json',
      cwd: './frontend-angular',
      url: 'http://localhost:4200/login',
      reuseExistingServer: true,
      timeout: 180000,
    },
  ],
  projects: [
    {
      name: 'vuetify',
      use: { ...devices['Desktop Chrome'], baseURL: 'http://localhost:5174' },
      testMatch: ['**/*vuetify.spec.ts'],
    },
    {
      name: 'angular',
      use: { ...devices['Desktop Chrome'], baseURL: 'http://localhost:4200' },
      testMatch: ['**/*angular.spec.ts'],
    },
  ],
})
