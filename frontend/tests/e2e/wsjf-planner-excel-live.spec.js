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

      // Se a tela já auto-selecionou o único recurso real, apenas validamos e seguimos.
      const atual = (await combo.inputValue().catch(() => '')).trim()
      if (atual) {
        if (valorEsperado) expect(atual).toMatch(valorEsperado)
        return atual
      }

      // Abre o menu pelo teclado e conclui a mesma ação que o usuário faria com
      // um clique na opção visível. Não usa force:true nem intercepta HTTP.
      await combo.focus()
      await combo.press('ArrowDown')
      // Escopado ao menu deste combobox (via aria-controls): a página tem outros
      // elementos com role="option" (ex.: navegação lateral) e um locator global
      // pode resolver para o item errado.
      const menuId = await combo.getAttribute('aria-controls')
      const menu = page.locator(`#${menuId}`)
      // Quando há um valor esperado (ex.: o grupo real do WSJF entre vários grupos
      // do tenant), seleciona a opção que bate com ele em vez de sempre a primeira.
      const option = valorEsperado ? menu.getByRole('option', { name: valorEsperado }).first() : menu.getByRole('option').first()
      await expect(option).toBeVisible({ timeout: 20_000 })
      const escolhido = (await option.textContent())?.trim() || ''
      await option.click()
      await expect(combo).not.toHaveValue('', { timeout: 20_000 })
      if (valorEsperado) await expect(combo).toHaveValue(valorEsperado, { timeout: 20_000 })
      return escolhido || (await combo.inputValue())
    }

    await escolherPrimeiro('Ambiente Power Platform de desenvolvimento')
    await escolherPrimeiro('Grupo ou equipe Microsoft 365', /ReqSys WSJF DEV/i)
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
