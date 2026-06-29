const { test, expect } = require('@playwright/test')
const { login, navegarMenu } = require('./helpers/auth')
const { mockResponsiveApis, loginDemo } = require('./helpers/responsiveMocks')
const {
  captureEvidence,
  ensureEvidenceDir,
  isStagingTarget,
  EVIDENCE_ROOT,
} = require('./helpers/evidence')

const ROTAS_EVIDENCIA = [
  { slug: 'dashboard', path: '/', testId: 'route-dashboard', titulo: 'Dashboard' },
  { slug: 'requisitos', path: '/requisitos', testId: 'route-requisitos', titulo: 'Requisitos' },
  { slug: 'pipeline', path: '/pipeline', testId: 'route-pipeline', titulo: 'Pipeline' },
  { slug: 'rastreabilidade', path: '/rastreabilidade', testId: 'route-rastreabilidade', titulo: 'Rastreabilidade' },
  { slug: 'relatorios', path: '/relatorios', testId: 'route-relatorios', titulo: 'Relatórios SSRS' },
  { slug: 'auditoria', path: '/auditoria', testId: 'route-auditoria', titulo: 'Auditoria' },
]

test.describe('evidência visual — ambiente local (demo + mocks)', () => {
  test.skip(isStagingTarget(), 'spec local não roda contra staging público')

  test.beforeEach(async ({ page }) => {
    await mockResponsiveApis(page)
    await page.setViewportSize({ width: 1366, height: 768 })
  })

  test('captura login, dashboard e navegação por temas', async ({ page }) => {
    ensureEvidenceDir('local')

    await page.goto('/login')
    await expect(page.getByTestId('route-login')).toBeVisible()
    await captureEvidence(page, '01-login', { subdir: 'local' })

    await loginDemo(page)
    await expect(page.getByTestId('route-dashboard')).toBeVisible()
    await captureEvidence(page, '02-dashboard', { subdir: 'local' })

    await page.getByTestId('nav-tema-requisitos').click()
    await page.getByTestId('nav-subgrupo-entrada').click()
    await captureEvidence(page, '03-nav-requisitos-entrada', { subdir: 'local' })

    await navegarMenu(page, { temaId: 'requisitos', subgrupoId: 'pipeline', tituloLink: /^Pipeline$/ })
    await expect(page.getByTestId('route-pipeline')).toBeVisible()
    await captureEvidence(page, '04-pipeline', { subdir: 'local' })

    await navegarMenu(page, { temaId: 'governanca', tituloLink: /^Relatórios SSRS$/ })
    await expect(page.getByTestId('route-relatorios')).toBeVisible()
    await captureEvidence(page, '05-relatorios', { subdir: 'local' })
  })

  test('captura rotas operacionais principais', async ({ page }) => {
    ensureEvidenceDir('local/rotas')
    await loginDemo(page)

    for (const rota of ROTAS_EVIDENCIA) {
      await page.goto(rota.path)
      await expect(page.getByTestId(rota.testId)).toBeVisible({ timeout: 15000 })
      await captureEvidence(page, rota.slug, { subdir: 'local/rotas', metadata: { titulo: rota.titulo } })
    }
  })
})

test.describe('evidência visual — staging (telas públicas + auth config)', () => {
  test.skip(!isStagingTarget(), 'spec staging requer E2E_BASE_URL apontando para STG')

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 })
  })

  test('captura tela de login corporativa e valida redirect URI', async ({ page, request }) => {
    ensureEvidenceDir('staging')

    await page.goto('/login')
    await expect(page.getByTestId('route-login')).toBeVisible()
    await expect(page.getByRole('button', { name: /entrar com conta microsoft/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /entrar \(demo\)/i })).toHaveCount(0)

    await captureEvidence(page, '01-login-microsoft', {
      subdir: 'staging',
      metadata: { ambiente: 'staging' },
    })

    const apiBase = process.env.E2E_API_URL || 'https://reqsys-api-stg.fly.dev'
    const configResponse = await request.get(`${apiBase}/v1/auth/config`)
    expect(configResponse.ok()).toBeTruthy()

    const payload = await configResponse.json()
    const authConfig = payload.data || payload

    expect(authConfig.azure_enabled).toBe(true)
    expect(authConfig.demo_login_enabled).toBe(false)
    expect(authConfig.expected_redirect_uri).toBe('https://reqsys-app-stg.fly.dev')

    const fs = require('node:fs')
    const path = require('node:path')
    fs.writeFileSync(
      path.join(EVIDENCE_ROOT, 'staging', 'auth-config.json'),
      JSON.stringify(authConfig, null, 2),
    )
  })

  test('captura callback redirect sem permanecer em callback.html', async ({ page }) => {
    ensureEvidenceDir('staging')

    await page.goto('/auth/callback.html?code=evidence-only&state=evidence-only')
    await expect(page).not.toHaveURL(/\/auth\/callback\.html/)
    await expect(page.locator('#app')).toBeAttached()

    await captureEvidence(page, '02-callback-redirect', {
      subdir: 'staging',
      fullPage: false,
      metadata: { nota: 'OAuth real não é automatizado; valida apenas redirect da SPA' },
    })
  })
})
