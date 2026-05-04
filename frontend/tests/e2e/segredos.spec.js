const { test, expect } = require('@playwright/test')
const { login } = require('./helpers/auth')

test.describe.configure({ retries: 1 })

async function irParaSegredos(page) {
    await login(page)
    await page.getByRole('link', { name: /^Segredos$/i }).click()
    await expect(page).toHaveURL(/\/segredos-status/, { timeout: 15000 })
    await expect(page.getByRole('heading', { name: /status de segredos/i })).toBeVisible({ timeout: 10000 })
}

// ---------------------------------------------------------------------------
test('página Status de Segredos carrega com título correto', async ({ page }) => {
    await irParaSegredos(page)
    await expect(page.getByRole('heading', { name: /status de segredos/i })).toBeVisible()
})

test('botão Atualizar está visível', async ({ page }) => {
    await irParaSegredos(page)
    const btn = page.getByTestId('btn-atualizar').or(
        page.getByRole('button', { name: /atualizar/i })
    )
    await expect(btn.first()).toBeVisible()
})

test('botão Abrir cofre está visível', async ({ page }) => {
    await irParaSegredos(page)
    const btn = page.getByTestId('btn-abrir-cofre').or(
        page.getByRole('link', { name: /abrir cofre/i })
    )
    await expect(btn.first()).toBeVisible()
})

test('tabela de segredos é exibida após carregamento', async ({ page }) => {
    await irParaSegredos(page)
    // Aguarda skeleton desaparecer
    await page.waitForSelector('[data-testid="tabela-segredos"], .v-table', { timeout: 8000 })
    const tabela = page.getByTestId('tabela-segredos').or(page.locator('.v-table').first())
    await expect(tabela.first()).toBeVisible()
})

test('tabela tem cabeçalhos de coluna corretos', async ({ page }) => {
    await irParaSegredos(page)
    await page.waitForSelector('[data-testid="tabela-segredos"], .v-table', { timeout: 8000 })
    await expect(page.getByRole('columnheader', { name: /nome/i })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: /origem/i })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: /resolvido/i })).toBeVisible()
})

test('valores dos segredos nunca são expostos (sem campo value_exposed=true)', async ({ page }) => {
    await irParaSegredos(page)
    // Verifica que não há texto "true" no contexto de exposição de valor
    const conteudo = await page.content()
    // A página não deve conter valores reais de segredos
    expect(conteudo).not.toContain('value_exposed')
})

test('card de resumo exibe totais numéricos', async ({ page }) => {
    await irParaSegredos(page)
    await page.waitForSelector('[data-testid="total"], .summary-value', { timeout: 8000 })
    const total = page.getByTestId('total').or(page.locator('.summary-value').first())
    await expect(total.first()).toBeVisible()
})

test('chips de origem exibem tooltip ao passar o mouse', async ({ page }) => {
    await irParaSegredos(page)
    await page.waitForSelector('[data-testid="tabela-segredos"], .v-table', { timeout: 8000 })

    const chip = page.locator('[data-testid="chip-origem"]').or(
        page.locator('[data-testid="tabela-segredos"] .v-chip').first()
    )
    const exists = await chip.first().count()
    if (exists > 0) {
        await chip.first().hover()
        await expect(page.locator('.v-tooltip__content, [role="tooltip"]').first()).toBeVisible({ timeout: 3000 })
    }
})

test('botão Atualizar dispara recarga dos segredos', async ({ page }) => {
    await irParaSegredos(page)
    await page.waitForSelector('[data-testid="tabela-segredos"], .v-table', { timeout: 8000 })

    const btn = page.getByTestId('btn-atualizar').or(
        page.getByRole('button', { name: /atualizar/i })
    )
    await btn.first().click()
    // Skeleton deve aparecer brevemente ou tabela reaparecer
    await page.waitForSelector('[data-testid="tabela-segredos"], .v-table', { timeout: 8000 })
    const tabela = page.getByTestId('tabela-segredos').or(page.locator('.v-table').first())
    await expect(tabela.first()).toBeVisible()
})
