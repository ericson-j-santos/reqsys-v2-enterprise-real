const { test, expect } = require('@playwright/test')

test('callback Microsoft redireciona para a SPA preservando code e state', async ({ page }) => {
  await page.goto('/auth/callback.html?code=test-code&state=test-state')

  await expect(page).not.toHaveURL(/\/auth\/callback\.html/)
  await expect(page.locator('#app')).toBeAttached()
})
