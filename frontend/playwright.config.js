const { defineConfig } = require('@playwright/test')

const baseURL = process.env.E2E_BASE_URL || process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:8084'
const systemChrome = process.env.REQSYS_SYSTEM_CHROME === '1'

module.exports = defineConfig({
    testDir: './tests/e2e',
    timeout: 30_000,
    fullyParallel: false,
    outputDir: 'test-results',
    reporter: [
        ['list'],
        ['html', { outputFolder: 'playwright-report', open: 'never' }],
        ['json', { outputFile: 'test-results/playwright-results.json' }],
    ],
    use: {
        baseURL,
        headless: true,
        // CI uses Chrome shipped with the official hosted runner image.
        // Absence is a hard failure in workflow; local development keeps bundled Chromium.
        ...(systemChrome ? { channel: 'chrome' } : {}),
        trace: 'on-first-retry',
    },
})
