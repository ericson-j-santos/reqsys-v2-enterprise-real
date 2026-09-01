const { test, expect } = require('@playwright/test')

const realJourney = process.env.REAL_USER_JOURNEY === 'true'

test.describe('aceite real WSJF Planner → Excel', () => {
  test.skip(!realJourney, 'Executado somente pelo gate de aceite real no DEV.')

  test('abre o DEV real, descobre recursos reais e valida sem mocks', async ({ page }) => {
    await page.goto('/login')

    const demoButton = page.getByRole('button', { name: /entrar \(demo\)/i })
    await expect(demoButton).toBeVisible({ timeout: 20_000 })
    await demoButton.click()
    await page.waitForURL((url) => !url.pathname.endsWith('/login'), { timeout: 20_000 })

    await page.goto('/hub-lowcode/wsjf/planner-excel/instalar')
    await expect(page.getByRole('heading', { name: 'Instalar Planner → Excel WSJF' })).toBeVisible({ timeout: 20_000 })
    await expect(page.getByText('Identidade Microsoft do ReqSys disponível para descoberta.')).toBeVisible({ timeout: 20_000 })
    await expect(page.getByText('O ReqSys ainda não possui identidade Microsoft configurada neste ambiente.')).toHaveCount(0)

    async function escolherPrimeiro(nome) {
      const combo = page.getByRole('combobox', { name: nome, exact: true })
      await expect(combo).toBeEnabled({ timeout: 20_000 })
      await combo.click()
      const option = page.getByRole('option').first()
      await expect(option).toBeVisible({ timeout: 20_000 })
      await option.click()
    }

    await escolherPrimeiro('Ambiente Power Platform de desenvolvimento')
    await escolherPrimeiro('Grupo ou equipe Microsoft 365')
    await escolherPrimeiro('Planner WSJF')

    const wsjf = page.getByRole('combobox', { name: 'Planilha WSJF', exact: true })
    await expect(wsjf).toBeEnabled({ timeout: 20_000 })
    await wsjf.click()
    await expect(page.getByRole('option', { name: /WSJF\.xlsx/i }).first()).toBeVisible({ timeout: 20_000 })
    await page.getByRole('option', { name: /WSJF\.xlsx/i }).first().click()

    await escolherPrimeiro('Planner')
    await escolherPrimeiro('Excel Online (Business)')

    await expect(page.getByText('Pronto para validar')).toBeVisible({ timeout: 20_000 })
    await page.getByRole('button', { name: 'Validar', exact: true }).click()
    await expect(page.getByText(/Validação aprovada/)).toBeVisible({ timeout: 30_000 })
    await expect(page.getByText(/tbDemandas/)).toBeVisible()

    // O teste não intercepta chamadas HTTP e não usa page.route().
    // Instalação/mutação fica fora desta etapa; o efeito de negócio é um gate separado.
  })
})
