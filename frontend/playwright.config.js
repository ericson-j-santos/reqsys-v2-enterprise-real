const { defineConfig } = require('@playwright/test')

module.exports = defineConfig({
    testDir: './tests/e2e',
    timeout: 30_000,
    fullyParallel: false,
    reporter: 'list',
    use: {
        baseURL: 'http://reqsys.localtest.me:8082',
        headless: true,
        trace: 'on-first-retry',
    },
})
