const { defineConfig } = require('@playwright/test')

const baseURL = process.env.E2E_BASE_URL || process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:8084'

module.exports = defineConfig({
    testDir: './tests/e2e',
    timeout: 30_000,
    fullyParallel: false,
    reporter: 'list',
    use: {
        baseURL,
        headless: true,
        trace: 'on-first-retry',
    },
})
