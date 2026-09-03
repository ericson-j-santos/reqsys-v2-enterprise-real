const fs = require('node:fs')
const { test, expect } = require('@playwright/test')

// Este spec testa especificamente o caminho de token delegado (MSAL) para
// "Conexões Microsoft". O login demo nao exercita esse fluxo.
//
// O arquivo apontado por MSAL_STORAGE_STATE_PATH e um envelope criado por
// scripts/setup-msal-storage-state.mjs. Ele contem o storageState nativo do
// Playwright e, separadamente, o sessionStorage usado pelo MSAL. Playwright
// nao persiste sessionStorage em storageState por conta propria.

const storageStatePath = process.env.MSAL_STORAGE_STATE_PATH || ''
const realJourney = process.env.REAL_USER_JOURNEY === 'true'

function loadAuthBundle(filePath) {
  if (!filePath || !fs.existsSync(filePath)) return null

  const parsed = JSON.parse(fs.readFileSync(filePath, 'utf8'))

  if (parsed?.schemaVersion !== 1) {
    throw new Error('MSAL storage state invalido: schemaVersion esperado = 1.')
  }
  if (!parsed.origin || typeof parsed.origin !== 'string') {
    throw new Error('MSAL storage state invalido: origin ausente.')
  }
  // Falha cedo caso o origin esteja malformado.
  new URL(parsed.origin)

  if (!parsed.storageState || !Array.isArray(parsed.storageState.cookies) || !Array.isArray(parsed.storageState.origins)) {
    throw new Error('MSAL storage state invalido: storageState do Playwright ausente ou malformado.')
  }
  if (!Array.isArray(parsed.sessionStorage) || parsed.sessionStorage.length === 0) {
    throw new Error('MSAL storage state invalido: sessionStorage ausente ou vazio.')
  }

  const malformedEntry = parsed.sessionStorage.some(
    (entry) => !entry || typeof entry.name !== 'string' || typeof entry.value !== 'string',
  )
  if (malformedEntry) {
    throw new Error('MSAL storage state invalido: entrada de sessionStorage malformada.')
  }

  const hasMsalCache = parsed.sessionStorage.some((entry) => entry.name.toLowerCase().includes('msal'))
  if (!hasMsalCache) {
    throw new Error('MSAL storage state invalido: cache MSAL nao encontrado no sessionStorage.')
  }

  return parsed
}

const authBundle = loadAuthBundle(storageStatePath)
const hasAuthBundle = Boolean(authBundle)

test.describe('aceite real WSJF — conexões via token delegado MSAL', () => {
  test.skip(!realJourney, 'Executado somente pelo gate de aceite real no DEV.')
  test.skip(!hasAuthBundle, 'Sem MSAL_STORAGE_STATE_PATH valido — rode npm run setup:msal-state e configure o secret.')

  test.use({
    storageState: authBundle?.storageState || { cookies: [], origins: [] },
  })

  test.beforeEach(async ({ context }) => {
    if (!authBundle) return

    await context.addInitScript(
      ({ origin, entries }) => {
        if (window.location.origin !== origin) return
        for (const { name, value } of entries) {
          window.sessionStorage.setItem(name, value)
        }
      },
      {
        origin: authBundle.origin,
        entries: authBundle.sessionStorage,
      },
    )
  })

  test('com sessão Microsoft real, conexões Planner/Excel resolvem de verdade (sem mocks)', async ({ page }) => {
    // storageState restaura cookies/localStorage e addInitScript restaura o
    // sessionStorage antes dos scripts da aplicacao rodarem.
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

    // O ponto real deste teste: com sessao Microsoft de verdade, o MSAL
    // consegue emitir um token delegado do Power Platform e o backend enxerga
    // as conexoes pessoais do usuario, diferente do login demo.
    await escolherPrimeiro('Planner')
    await escolherPrimeiro('Excel Online (Business)')

    const resumoCard = page.locator('.v-card').filter({ hasText: 'Resumo da conexão' })
    await expect(resumoCard.getByText('Conectada')).toHaveCount(2, { timeout: 20_000 })
    await expect(resumoCard.getByText('Pendente')).toHaveCount(0)

    // O objetivo deste teste termina aqui: provar que a descoberta de
    // conexoes via token delegado funciona ponta a ponta contra o tenant
    // real. "Validar"/"Instalar fluxo" tambem exigem status.alm_configurado
    // (GITHUB_PAT + repositorio ALM no backend) — uma precondicao separada,
    // sem relacao com MSAL/conexoes, e fora do escopo deste spec.
  })
})
