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

    async function escolherPrimeiro(nome, valorEsperado = null) {
      const combo = page.getByRole('combobox', { name: nome, exact: true })
      await expect(combo).toBeEnabled({ timeout: 20_000 })

      // Vuetify mantém um <input role="combobox"> sob o wrapper visual. Clicar
      // diretamente nesse input pode ser interceptado pelo v-field. Se a tela já
      // auto-selecionou o único recurso real, apenas validamos e seguimos.
      const atual = (await combo.inputValue().catch(() => '')).trim()
      if (atual) {
        if (valorEsperado) expect(atual).toMatch(valorEsperado)
        return atual
      }

      // Teclado exercita o mesmo componente real sem usar force:true e sem
      // mascarar problemas de interação do usuário.
      await combo.focus()
      await combo.press('ArrowDown')
      const option = page.getByRole('option').first()
      await expect(option).toBeVisible({ timeout: 20_000 })
      const escolhido = (await option.textContent())?.trim() || ''
      await combo.press('Enter')
      await expect(combo).not.toHaveValue('', { timeout: 20_000 })
      if (valorEsperado) await expect(combo).toHaveValue(valorEsperado, { timeout: 20_000 })
      return escolhido || (await combo.inputValue())
    }

    await escolherPrimeiro('Ambiente Power Platform de desenvolvimento')
    await escolherPrimeiro('Grupo ou equipe Microsoft 365')
    await escolherPrimeiro('Planner WSJF')
    await escolherPrimeiro('Planilha WSJF', /WSJF\.xlsx/i)
    await escolherPrimeiro('Planner')
    await escolherPrimeiro('Excel Online (Business)')

    await expect(page.getByText('Pronto para validar')).toBeVisible({ timeout: 20_000 })
    await page.getByRole('button', { name: 'Validar', exact: true }).click()
    await expect(page.getByText(/Validação aprovada/)).toBeVisible({ timeout: 30_000 })
    await expect(page.getByText(/tbDemandas/).first()).toBeVisible()

    // Este teste não intercepta chamadas HTTP e não usa page.route().
    // Instalação/mutação fica fora desta etapa; o efeito de negócio é um gate separado.
  })
})
