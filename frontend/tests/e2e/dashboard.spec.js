const { test, expect } = require('@playwright/test')

async function login(page) {
    await page.goto('/login', { waitUntil: 'domcontentloaded' })

    await page.getByLabel('E-mail').fill('ericsonjosedossantos@tieri659.onmicrosoft.com')
    await page.getByLabel('Senha').fill('admin123')
    await page.getByRole('button', { name: 'Entrar' }).click()

    await expect(page).toHaveURL(/\/$/)
    await expect(page.getByRole('heading', { name: 'Dashboard de Requisitos' })).toBeVisible()
}

test('dashboard exibe cards, informações e tooltips', async ({ page }) => {
    await login(page)

    const main = page.getByRole('main')
    await expect(main.getByText('Requisitos', { exact: true })).toBeVisible()
    await expect(main.getByText('Em análise', { exact: true })).toBeVisible()
    await expect(main.getByText('Informações do sistema', { exact: true })).toBeVisible()
    await expect(main.getByText('Pipeline operacional', { exact: true })).toBeVisible()

    await page.getByLabel('Informação da métrica').first().hover()
    await expect(page.getByText('Quantidade total de requisitos cadastrados.')).toBeVisible()

    await page.setViewportSize({ width: 390, height: 844 })
    await expect(main.getByText('Requisitos', { exact: true })).toBeVisible()
    await expect(main.getByText('Informações do sistema', { exact: true })).toBeVisible()
})
