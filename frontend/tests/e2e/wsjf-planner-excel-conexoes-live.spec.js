const fs = require('node:fs')
const { test, expect } = require('@playwright/test')

// Este spec testa especificamente o caminho de token delegado (MSAL) para
// "Conexões Microsoft" — o pedaço que wsjf-planner-excel-live.spec.js NÃO
// consegue exercitar porque loga via "Entrar (demo)" (nunca passa pelo MSAL).
//
// Precisa de uma sessão Microsoft real e pré-autenticada (cookies +
// sessionStorage onde o MSAL guarda o cache de tokens), capturada com
// scripts/setup-msal-storage-state.mjs e apontada via MSAL_STORAGE_STATE_PATH.
// Sem isso, pula — de propósito, para não fingir sucesso sem evidência real.

const storageStatePath = process.env.MSAL_STORAGE_STATE_PATH || ''
const hasStorageState = Boolean(storageStatePath) && fs.existsSync(storageStatePath)
const realJourney = process.env.REAL_USER_JOURNEY === 'true'

test.describe('aceite real WSJF — conexões via token delegado MSAL', () => {
  test.skip(!realJourney, 'Executado somente pelo gate de aceite real no DEV.')
  test.skip(!hasStorageState, 'Sem MSAL_STORAGE_STATE_PATH válido — rode scripts/setup-msal-storage-state.mjs e configure o secret.')

  test.use({ storageState: storageStatePath })

  test('com sessão Microsoft real, conexões Planner/Excel resolvem de verdade (sem mocks)', async ({ page }) => {
    // Já autenticado via storageState — vai direto para a tela, sem login demo.
    await page.goto('/hub-lowcode/wsjf/planner-excel/instalar')
    await expect(page.getByRole('heading', { name: 'Instalar Planner → Excel WSJF' })).toBeVisible({ timeout: 20_000 })
    await expect(page.getByText('Identidade Microsoft do ReqSys disponível para descoberta.')).toBeVisible({ timeout: 20_000 })

    async function escolherPrimeiro(nome, valorEsperado = null) {
      const combo = page.getByRole('combobox', { name: nome, exact: true })
      await expect(combo).toBeEnabled({ timeout: 20_000 })

      const atual = (await combo.inputValue().catch(() => '')).trim()
      if (atual) {
        if (valorEsperado) expect(atual).toMatch(valorEsperado)
        return atual
      }

      const menuId = await combo.getAttribute('aria-controls')
      const menu = page.locator(`#${menuId}`)
      await combo.focus()
      await combo.press('ArrowDown')
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

    // O ponto real deste teste: com sessão Microsoft de verdade, o MSAL
    // consegue emitir um token delegado (Connectivity.Connections.Read) e o
    // backend enxerga as conexões pessoais do usuário — diferente do login
    // demo, que nunca chega aqui com dado real.
    await escolherPrimeiro('Planner')
    await escolherPrimeiro('Excel Online (Business)')

    const resumoCard = page.locator('.v-card').filter({ hasText: 'Resumo da conexão' })
    await expect(resumoCard.getByText('Conectada')).toHaveCount(2, { timeout: 20_000 })
    await expect(resumoCard.getByText('Pendente')).toHaveCount(0)

    await expect(page.getByText('Pronto para validar')).toBeVisible({ timeout: 20_000 })
    await page.getByRole('button', { name: 'Validar', exact: true }).click()
    await expect(page.getByText(/Validação aprovada/)).toBeVisible({ timeout: 30_000 })

    // Instalação real fica fora deste teste — só prova que a descoberta de
    // conexões via token delegado funciona de ponta a ponta contra o tenant real.
  })
})
