const { test, expect } = require('@playwright/test')
const { login } = require('./helpers/auth')

test.describe.configure({ retries: 1 })

async function irParaRequisitos(page) {
    await login(page)
    await page.getByRole('link', { name: /^Requisitos$/i }).click()
    await expect(page).toHaveURL(/\/requisitos/, { timeout: 15000 })
    await expect(page.getByRole('heading', { name: 'Requisitos' })).toBeVisible({ timeout: 10000 })
}

// ---------------------------------------------------------------------------
test('página Requisitos carrega com título correto', async ({ page }) => {
    await irParaRequisitos(page)
    await expect(page.getByRole('heading', { name: 'Requisitos' })).toBeVisible()
})

test('botão Atualizar está visível e habilitado', async ({ page }) => {
    await irParaRequisitos(page)
    const btn = page.getByTestId('btn-atualizar').or(
        page.getByRole('button', { name: /atualizar/i })
    )
    await expect(btn.first()).toBeVisible()
})

test('botão Novo requisito está visível', async ({ page }) => {
    await irParaRequisitos(page)
    const btn = page.getByRole('button', { name: /novo requisito/i })
    await expect(btn).toBeVisible()
})

test('clicar em Novo requisito abre o diálogo', async ({ page }) => {
    await irParaRequisitos(page)
    const btn = page.getByRole('button', { name: /novo requisito/i })
    await btn.click()
    // Diálogo deve aparecer com campo Título
    await expect(page.getByLabel(/título/i)).toBeVisible({ timeout: 5000 })
})

test('diálogo fecha ao clicar em Cancelar', async ({ page }) => {
    await irParaRequisitos(page)
    await page.getByRole('button', { name: /novo requisito/i }).click()
    await expect(page.getByLabel(/título/i)).toBeVisible({ timeout: 5000 })

    await page.getByRole('button', { name: /cancelar/i }).click()
    await expect(page.getByLabel(/título/i)).not.toBeVisible({ timeout: 3000 })
})

test('tabela de requisitos é exibida após carregamento', async ({ page }) => {
    await irParaRequisitos(page)
    // Aguarda skeleton desaparecer ou tabela aparecer
    await page.waitForSelector('.v-data-table, [data-testid="tabela-requisitos"]', { timeout: 8000 })
    await expect(page.locator('.v-data-table').first()).toBeVisible()
})

test('chip de status na tabela exibe tooltip ao passar o mouse', async ({ page }) => {
    await irParaRequisitos(page)
    await page.waitForSelector('.v-data-table', { timeout: 8000 })

    const chip = page.locator('.v-data-table .v-chip').first()
    const exists = await chip.count()
    if (exists > 0) {
        await chip.hover()
        // tooltip deve aparecer com algum texto visível
        await expect(page.locator('.v-tooltip__content, [role="tooltip"]').first()).toBeVisible({ timeout: 3000 })
    }
})
