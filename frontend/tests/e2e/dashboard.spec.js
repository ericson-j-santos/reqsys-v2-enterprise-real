const { test, expect } = require('@playwright/test')
const { login } = require('./helpers/auth')

test('dashboard exibe cards, informações e tooltips', async ({ page }) => {
    await login(page)

    // Cards de métricas por classe específica, evitando ambiguidade com o menu
    await expect(page.locator('.metric-title').filter({ hasText: 'Requisitos' }).first()).toBeVisible()
    await expect(page.locator('.metric-title').filter({ hasText: 'Em análise' }).first()).toBeVisible()
    await expect(page.getByText('Informações do sistema', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('Pipeline operacional', { exact: true }).first()).toBeVisible()

    await page.getByLabel('Informação da métrica').first().hover()
    await expect(page.getByText('Quantidade total de requisitos cadastrados.')).toBeVisible()

    await page.setViewportSize({ width: 390, height: 844 })
    await expect(page.locator('.metric-title').filter({ hasText: 'Requisitos' }).first()).toBeVisible()
    await expect(page.getByText('Informações do sistema', { exact: true }).first()).toBeVisible()
})

test('hover no card exibe mini-preview com link de navegação', async ({ page }) => {
    await login(page)

    // Passa mouse sobre o primeiro card de métrica
    const card = page.locator('.metric-interactive').first()
    await card.hover()

    // Mini-preview deve aparecer com botão "Ver detalhes"
    await expect(page.getByRole('button', { name: 'Ver detalhes' }).first()).toBeVisible({ timeout: 3000 })
})

test('clique em "Ver detalhes" no card navega para a rota correta', async ({ page }) => {
    await login(page)

    const card = page.locator('.metric-interactive').first()
    await card.hover()

    await page.getByRole('button', { name: 'Ver detalhes' }).first().click()

    // Deve navegar para uma rota diferente de /
    await expect(page).not.toHaveURL(/^\/$/)
})

test('botão de ícone no card navega diretamente', async ({ page }) => {
    await login(page)

    const iconBtn = page.locator('.metric-value-row button').first()
    await iconBtn.click()

    await expect(page).not.toHaveURL(/^\/$/)
})

test('dashboard responsivo em 600px mantém layout funcional', async ({ page }) => {
    await page.setViewportSize({ width: 600, height: 900 })
    await login(page)

    await expect(page.locator('.metric-title').filter({ hasText: 'Requisitos' }).first()).toBeVisible()
    await expect(page.getByText('Pipeline operacional', { exact: true }).first()).toBeVisible()
})

test('menu lateral de navegação está presente', async ({ page }) => {
    await login(page)

    await expect(page.getByRole('link', { name: 'Relatórios SSRS' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Rastreabilidade' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Auditoria' })).toBeVisible()
})
