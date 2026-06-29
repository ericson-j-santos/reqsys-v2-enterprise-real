const { defineConfig, devices } = require('@playwright/test')

const baseURL = process.env.E2E_BASE_URL || process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:8084'
const evidenceMode = process.env.E2E_EVIDENCE_MODE === '1' || process.env.E2E_EVIDENCE_MODE === 'true'
const visualMode = process.env.E2E_VISUAL_MODE === '1' || process.env.E2E_VISUAL_MODE === 'true'

module.exports = defineConfig({
    testDir: './tests/e2e',
    timeout: (evidenceMode || visualMode) ? 60_000 : 30_000,
    fullyParallel: false,
    snapshotPathTemplate: '{testDir}/{testFileDir}/{testFileName}-snapshots/{arg}-{projectName}{ext}',
    outputDir: evidenceMode ? 'test-results/evidence-run' : 'test-results',
    reporter: evidenceMode
        ? [['list'], ['html', { open: 'never', outputFolder: 'playwright-report/evidence' }]]
        : visualMode
            ? [['list'], ['html', { open: 'never', outputFolder: 'playwright-report/visual' }]]
            : 'list',
    expect: {
        toHaveScreenshot: {
            animations: 'disabled',
            maxDiffPixelRatio: Number(process.env.E2E_VISUAL_MAX_DIFF_RATIO || 0.02),
            threshold: Number(process.env.E2E_VISUAL_THRESHOLD || 0.25),
            caret: 'hide',
        },
    },
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
    ],
    use: {
        baseURL,
        headless: true,
        trace: (evidenceMode || visualMode) ? 'retain-on-failure' : 'on-first-retry',
        screenshot: evidenceMode ? 'on' : 'only-on-failure',
        video: (evidenceMode || visualMode) ? 'retain-on-failure' : 'off',
        locale: 'pt-BR',
        timezoneId: 'America/Sao_Paulo',
        deviceScaleFactor: 1,
    },
})
