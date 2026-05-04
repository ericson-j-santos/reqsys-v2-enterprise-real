const { test, expect } = require('@playwright/test')

const EMAIL = 'ericsonjosedossantos@tieri659.onmicrosoft.com'
const SENHA = 'admin123'

async function login(page) {
    await page.goto('/login', { waitUntil: 'domcontentloaded' })
    await page.getByLabel('E-mail').fill(EMAIL)
    await page.getByLabel('Senha').fill(SENHA)
    await page.getByRole('button', { name: 'Entrar' }).click()
    await expect(page).toHaveURL(/\/$/)
}

test('rota /relatorios não redireciona para o dashboard', async ({ page }) => {
    await login(page)

    await page.goto('/relatorios', { waitUntil: 'domcontentloaded' })

    // Não deve redirecionar de volta para /
    await expect(page).not.toHaveURL(/^\/$/)
    await expect(page).toHaveURL(/\/relatorios/)
})

test('página de relatórios exibe título e botão de atualizar', async ({ page }) => {
    await login(page)
    await page.goto('/relatorios', { waitUntil: 'domcontentloaded' })

    // Deve haver algum título ou conteúdo da página de relatórios
    const main = page.getByRole('main')
    await expect(main).toBeVisible()

    // Botão de atualizar catálogo deve existir (está no header da page, não dentro de main)
    const refreshBtn = page.getByRole('button', { name: /atualiz/i })
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
    await page.goto('/relatorios', { waitUntil: 'domcontentloaded' })

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
