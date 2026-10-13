const fs = require('node:fs')
const { test, expect } = require('@playwright/test')
const { sanitizeStorageState } = require('../../scripts/msal-storage-state-sanitizer.cjs')

// Executado somente no workflow de verificacao publica. Nenhum mock, rota
// interceptada, login demo, token artificioso ou escrita no sistema.
const DEV_URL = 'https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev/'
const mode = process.env.REQSYS_PUBLISHED_SEARCH_E2E || ''
const validMode = ['anonymous', 'authenticated'].includes(mode)

if (validMode && process.env.E2E_BASE_URL !== DEV_URL) {
  throw new Error('PUBLIC_SEARCH_E2E_TARGET_MISMATCH')
}

function msalState() {
  const file = process.env.MSAL_STORAGE_STATE_PATH
  if (!file || !fs.existsSync(file)) throw new Error('PUBLIC_SEARCH_MSAL_STATE_UNAVAILABLE')
  let bundle
  try {
    bundle = JSON.parse(fs.readFileSync(file, 'utf8'))
  } catch {
    throw new Error('PUBLIC_SEARCH_MSAL_STATE_INVALID')
  }
  if (bundle?.schemaVersion !== 1 || bundle.origin !== new URL(DEV_URL).origin) {
    throw new Error('PUBLIC_SEARCH_MSAL_ORIGIN_MISMATCH')
  }
  if (!Array.isArray(bundle?.sessionStorage) || !bundle.sessionStorage.some(
    entry => entry && typeof entry.name === 'string' && entry.name.toLowerCase().includes('msal'),
  )) {
    throw new Error('PUBLIC_SEARCH_MSAL_CACHE_MISSING')
  }
  if (!Array.isArray(bundle?.storageState?.cookies) || !Array.isArray(bundle?.storageState?.origins)) {
    throw new Error('PUBLIC_SEARCH_MSAL_STORAGE_INVALID')
  }
  return { ...bundle, storageState: sanitizeStorageState(bundle.storageState, bundle.origin) }
}

const authBundle = mode === 'authenticated' ? msalState() : null

const cleanSession = { cookies: [], origins: [] }

test.describe('ReqSys Pages DEV — prova pública sem autenticação', () => {
  test.skip(mode !== 'anonymous', 'Executado pelo job público dedicado.')
  test.use({ storageState: cleanSession })

  test('carrega o login corporativo sem mostrar a lupa ou liberar login demo', async ({ page }, testInfo) => {
    const authConfigResponsePromise = page.waitForResponse(response =>
      response.request().method() === 'GET' &&
      new URL(response.url()).pathname.endsWith('/api/v1/auth/config'),
    { timeout: 30_000 })
    const response = await page.goto(DEV_URL, { waitUntil: 'domcontentloaded' })
    expect(response?.status()).toBe(200)
    await expect(page.getByTestId('route-login')).toBeVisible({ timeout: 25_000 })
    await expect(page.getByRole('button', { name: 'Entrar com conta Microsoft' })).toBeVisible({ timeout: 25_000 })

    // Capturar a pagina anonima mesmo se o controle negativo reprovar.
    // A mascara impede publicar e-mail ou senha predefinidos em artefatos.
    await page.screenshot({
      path: testInfo.outputPath('public-login.png'),
      fullPage: true,
      mask: [page.locator('.login-card input')],
      maskColor: '#000000',
    })

    const authResponse = await authConfigResponsePromise
    const configPayload = await authResponse.json()
    const config = configPayload?.data ?? configPayload
    const authUrl = new URL(authResponse.url())
    const signedRuntimeOrigin = authUrl.protocol === 'https:' && authUrl.hostname.endsWith('.trycloudflare.com')
    // Evidencia somente sinalizadores publicos, nunca tokens/cookies/JSON completo.
    console.info(JSON.stringify({
      check: 'public_auth_flags',
      http: authResponse.status(),
      signed_runtime: signedRuntimeOrigin,
      azure_enabled: typeof config?.azure_enabled === 'boolean' ? config.azure_enabled : 'invalid_type',
      demo_login_enabled: typeof config?.demo_login_enabled === 'boolean' ? config.demo_login_enabled : 'invalid_type',
    }))
    expect(authResponse.status()).toBe(200)
    expect(signedRuntimeOrigin).toBe(true)
    expect(config?.azure_enabled).toBe(true)
    expect(config?.demo_login_enabled).toBe(false)
    await expect(page.getByRole('button', { name: /entrar \(demo\)/i })).toHaveCount(0)
    await expect(page.getByTestId('global-search-trigger-desktop')).toHaveCount(0)
    expect(new URL(page.url()).pathname).toMatch(/^\/reqsys-v2-enterprise-real\/dev\/login$/)
  })

  test('entrega bundle publicado contendo os controles da lupa', async ({ request }) => {
    const htmlResponse = await request.get(DEV_URL)
    expect(htmlResponse.status()).toBe(200)
    const html = await htmlResponse.text()
    const scriptSrc = [...html.matchAll(/<script\b[^>]*\bsrc=["']([^"']+\.js)["']/gi)].map(x => x[1])
    expect(scriptSrc.length).toBeGreaterThan(0)
    const bodies = await Promise.all(scriptSrc.map(async src => {
      const assetURL = new URL(src, DEV_URL)
      expect(assetURL.origin).toBe(new URL(DEV_URL).origin)
      expect(assetURL.pathname.startsWith('/reqsys-v2-enterprise-real/dev/assets/')).toBe(true)
      const asset = await request.get(assetURL.toString())
      expect(asset.status()).toBe(200)
      return asset.text()
    }))
    const javascript = bodies.join('\n')
    expect(javascript).toContain('global-search-trigger-desktop')
    expect(javascript).toContain('global-search-trigger-mobile')
    expect(javascript).toContain('global-search-dialog')
  })
})

test.describe('ReqSys Pages DEV — interação real com sessão Microsoft autorizada', () => {
  test.skip(mode !== 'authenticated', 'Requer sessão Microsoft DEV verdadeira e ainda válida.')
  test.use({ storageState: authBundle?.storageState || cleanSession })

  test.beforeEach(async ({ context }) => {
    if (!authBundle) return
    await context.addInitScript(({ origin, entries }) => {
      if (window.location.origin !== origin) return
      for (const entry of entries) {
        window.sessionStorage.setItem(entry.name, entry.value)
      }
    }, { origin: authBundle.origin, entries: authBundle.sessionStorage })
  })

  test('login real, lupa, resultados, navegação, teclado e visualização móvel', async ({ page }) => {
    // O token ReqSys é obtido novamente da API real a partir da sessão MSAL.
    // Exigir POST Azure 200 impede confundir restauração de cache com login real.
    const azureLogin = page.waitForResponse(response =>
      response.url().endsWith('/api/v1/auth/azure') &&
      response.request().method() === 'POST' && response.status() === 200,
    { timeout: 30_000 })
    await page.goto(DEV_URL, { waitUntil: 'domcontentloaded' })
    await azureLogin
    await expect(page.getByTestId('global-search-trigger-desktop')).toBeVisible({ timeout: 30_000 })
    await page.getByTestId('global-search-trigger-desktop').click()
    const input = page.getByTestId('global-search-input').locator('input')
    await expect(input).toBeFocused()
    await input.fill('RASTREABILIDADE')
    const result = page.getByTestId('global-search-result').filter({
      has: page.getByText('Rastreabilidade', { exact: true }),
    })
    await expect(result).toHaveCount(1)
    await result.click()
    await expect(page).toHaveURL(new URL('rastreabilidade', DEV_URL).toString())
    await expect(page.getByTestId('global-search-dialog')).not.toBeVisible()

    await page.keyboard.press('Control+k')
    const shortcutInput = page.getByTestId('global-search-input').locator('input')
    await shortcutInput.fill('painel de projetos')
    await shortcutInput.press('Enter')
    await expect(page).toHaveURL(new URL('painel-projetos', DEV_URL).toString())
    await page.keyboard.press('Control+k')
    await page.getByTestId('global-search-input').locator('input').fill('termo-impossivel-reqsys-e2e-2026')
    await expect(page.getByTestId('global-search-empty')).toBeVisible()
    await page.getByTestId('global-search-close').click()
    await page.setViewportSize({ width: 390, height: 844 })
    await page.getByTestId('global-search-trigger-mobile').click()
    await page.getByTestId('global-search-input').locator('input').fill('qualidade ia')
    await expect(page.getByTestId('global-search-result').filter({
      has: page.getByText('Qualidade IA', { exact: true }),
    })).toBeVisible()
  })
})
