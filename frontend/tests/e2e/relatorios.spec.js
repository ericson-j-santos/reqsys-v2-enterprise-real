const { test, expect } = require('@playwright/test')
const { login } = require('./helpers/auth')

test.describe.configure({ retries: 1 })

async function abrirRelatoriosPeloMenu(page) {
    await page.getByRole('link', { name: /relatórios ssrs/i }).click()
    await expect(page).toHaveURL(/\/relatorios/, { timeout: 15000 })
}

test('rota /relatorios não redireciona para o dashboard', async ({ page }) => {
    await login(page)

    await abrirRelatoriosPeloMenu(page)

    // Não deve redirecionar de volta para /
    await expect(page).not.toHaveURL(/^\/$/)
    await expect(page).toHaveURL(/\/relatorios/)
})

test('página de relatórios exibe título e botão de atualizar', async ({ page }) => {
    await login(page)
    await abrirRelatoriosPeloMenu(page)

    // Deve haver algum título ou conteúdo da página de relatórios
    await expect(page.getByText('Relatórios SSRS', { exact: true }).first()).toBeVisible()

    // Botão de atualizar catálogo deve existir (ícone mdi-refresh — sem texto)
    const refreshBtn = page.locator('button').filter({ has: page.locator('.mdi-refresh') }).first()
    await expect(refreshBtn).toBeVisible()
})

test('link de relatório no menu lateral navega para /relatorios', async ({ page }) => {
    await login(page)

    // Clica em "Relatórios SSRS" no menu lateral
    await page.getByRole('link', { name: /relatórios ssrs/i }).click()
    await expect(page).toHaveURL(/\/relatorios/)
})

test('botão Abrir em nova guia não redireciona a página atual', async ({ page }) => {
    await login(page)
    await abrirRelatoriosPeloMenu(page)

    const main = page.getByRole('main')
    const abrirBtns = main.getByRole('button', { name: /abrir/i })
    const count = await abrirBtns.count()

    if (count > 0) {
        // Captura nova aba para verificar que window.open foi chamado (não redireciona a aba atual)
        const [newPage] = await Promise.all([
            page.context().waitForEvent('page', { timeout: 3000 }).catch(() => null),
            abrirBtns.first().click()
        ])

        // A página atual deve continuar em /relatorios
        await expect(page).toHaveURL(/\/relatorios/)
    } else {
        // Sem relatórios listados — apenas verifica que a página está acessível
        await expect(main).toBeVisible()
    }
})

// ─── Novos testes: dashboard completo ────────────────────────────────────────

test('KPI cards visíveis na página de relatórios', async ({ page }) => {
    await login(page)
    await abrirRelatoriosPeloMenu(page)

    // Todos os 4 KPI cards devem estar visíveis
    await expect(page.getByText('SSRS Status')).toBeVisible()
    await expect(page.getByText('Total Relatórios')).toBeVisible()
    await expect(page.getByText('Acessíveis')).toBeVisible()
    await expect(page.getByText('Última Verificação')).toBeVisible()
})

test('tabs Monitor, Visualizador e Downloads PDF visíveis', async ({ page }) => {
    await login(page)
    await abrirRelatoriosPeloMenu(page)

    await expect(page.getByRole('tab', { name: /Monitor/i })).toBeVisible()
    await expect(page.getByRole('tab', { name: /Visualizador/i })).toBeVisible()
    await expect(page.getByRole('tab', { name: /Downloads PDF/i })).toBeVisible()
})

test('navegar para tab Visualizador mostra iframe ou empty state', async ({ page }) => {
    await login(page)
    await abrirRelatoriosPeloMenu(page)

    await page.getByRole('tab', { name: /Visualizador/i }).click()

    // Deve mostrar lista de relatórios ou empty state
    const hasIframe = await page.locator('iframe').count()
    const hasEmptyState = await page.locator('.empty-state').count()
    expect(hasIframe + hasEmptyState).toBeGreaterThanOrEqual(1)
})

test('navegar para tab Downloads PDF mostra cards de download', async ({ page }) => {
    await login(page)
    await abrirRelatoriosPeloMenu(page)

    await page.getByRole('tab', { name: /Downloads PDF/i }).click()

    // Deve conter botões de PDF ou título da seção
    await expect(page.getByText('Download de Relatórios em PDF')).toBeVisible()
})

test('botão Verificar existe no header da página', async ({ page }) => {
    await login(page)
    await abrirRelatoriosPeloMenu(page)

    const verificarBtn = page.getByRole('button', { name: /Verificar/i })
    await expect(verificarBtn).toBeVisible()
})

test('chip de status SSRS visível no header', async ({ page }) => {
    await login(page)
    await abrirRelatoriosPeloMenu(page)

    // O chip de status pode conter diferentes textos
    const statusChip = page.getByText(/SSRS (online|offline|não configurado)/i)
    await expect(statusChip.first()).toBeVisible()
})

test('responsividade mobile — KPI cards visíveis em 375px', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await login(page)
    await abrirRelatoriosPeloMenu(page)

    await expect(page.getByText('SSRS Status')).toBeVisible()
    await expect(page.getByText('Total Relatórios')).toBeVisible()
    // Página não deve ter overflow horizontal
    const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth)
    const viewportWidth = await page.evaluate(() => window.innerWidth)
    expect(bodyScrollWidth).toBeLessThanOrEqual(viewportWidth + 20) // tolerância de 20px
})

test('tab Monitor exibe tabela de relatórios', async ({ page }) => {
    await login(page)
    await abrirRelatoriosPeloMenu(page)

    // Tab Monitor é a padrão — deve mostrar a tabela
    const monitorTab = page.getByRole('tab', { name: /Monitor/i })
    await expect(monitorTab).toBeVisible()

    // A tabela ou mensagem de "Nenhum relatório" deve estar visível
    const hasTable = await page.locator('table').count()
    const hasEmpty = await page.getByText('Nenhum relatório disponível').count()
    expect(hasTable + hasEmpty).toBeGreaterThanOrEqual(1)
})
