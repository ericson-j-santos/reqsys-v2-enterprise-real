const { defineConfig } = require('@playwright/test')

const baseURL = process.env.E2E_BASE_URL || process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:8084'
const evidenceMode = process.env.E2E_EVIDENCE_MODE === '1' || process.env.E2E_EVIDENCE_MODE === 'true'

module.exports = defineConfig({
    testDir: './tests/e2e',
    timeout: evidenceMode ? 60_000 : 30_000,
    fullyParallel: false,
    outputDir: evidenceMode ? 'test-results/evidence-run' : 'test-results',
    reporter: evidenceMode
        ? [['list'], ['html', { open: 'never', outputFolder: 'playwright-report/evidence' }]]
        : 'list',
    use: {
        baseURL,
        headless: true,
        trace: evidenceMode ? 'retain-on-failure' : 'on-first-retry',
        screenshot: evidenceMode ? 'on' : 'only-on-failure',
        video: evidenceMode ? 'retain-on-failure' : 'off',
    },
})
