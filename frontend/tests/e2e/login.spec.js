const { test, expect } = require('@playwright/test')

test('realiza login e redireciona para dashboard', async ({ page }) => {
    await page.goto('/login', { waitUntil: 'domcontentloaded' })

    await page.getByLabel('E-mail').fill('ericsonjosedossantos@tieri659.onmicrosoft.com')
    await page.getByLabel('Senha').fill('admin123')
    await page.getByRole('button', { name: 'Entrar' }).click()

    await expect(page).toHaveURL(/\/$/)
    await expect(page.getByRole('heading', { name: 'Dashboard de Requisitos' })).toBeVisible()

    const token = await page.evaluate(() => localStorage.getItem('reqsys_token'))
    expect(token).toBeTruthy()
})
