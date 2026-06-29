const { test, expect } = require('@playwright/test')
const { mockResponsiveApis, loginDemo } = require('./helpers/responsiveMocks')
const { navegarMenu } = require('./helpers/auth')
const { isStagingTarget } = require('./helpers/evidence')
const { prepareVisualPage, assertVisualSnapshot } = require('./helpers/visualSnapshot')

/**
 * Regressão visual pixel-a-pixel com baselines versionados.
 * Roda apenas em ambiente local com mocks — STG é instável (CDN, fontes, deploy).
 */
test.describe('regressão visual — baselines versionados', () => {
  test.skip(isStagingTarget(), 'snapshots exigem ambiente local estável com mocks')

  test.beforeEach(async ({ page }) => {
    await mockResponsiveApis(page)
    await prepareVisualPage(page)
  })

  test('login — card corporativo', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByTestId('route-login')).toBeVisible()

    await assertVisualSnapshot(page, 'login-card', {
      locator: page.locator('.login-card'),
    })
  })

  test('dashboard — métricas e pipeline', async ({ page }) => {
    await loginDemo(page)
    await expect(page.getByTestId('route-dashboard')).toBeVisible()

    await assertVisualSnapshot(page, 'dashboard-main', {
      locator: page.locator('.dashboard-operacional'),
    })
  })

  test('navegação — drawer tema Requisitos / Entrada', async ({ page }) => {
    await loginDemo(page)

    await page.getByTestId('nav-tema-requisitos').click()
    await page.getByTestId('nav-subgrupo-entrada').click()

    await assertVisualSnapshot(page, 'nav-requisitos-entrada', {
      locator: page.locator('.req-drawer'),
    })
  })

  test('requisitos — lista vazia mockada', async ({ page }) => {
    await loginDemo(page)
    await page.goto('/requisitos')
    await expect(page.getByTestId('route-requisitos')).toBeVisible()

    await assertVisualSnapshot(page, 'requisitos-lista', {
      locator: page.locator('.req-main'),
    })
  })

  test('pipeline — painel operacional', async ({ page }) => {
    await loginDemo(page)
    await navegarMenu(page, { temaId: 'requisitos', subgrupoId: 'pipeline', tituloLink: /^Pipeline$/ })
    await expect(page.getByTestId('route-pipeline')).toBeVisible()

    await assertVisualSnapshot(page, 'pipeline-painel', {
      locator: page.locator('.req-main'),
    })
  })

  test('relatórios — painel SSRS', async ({ page }) => {
    await loginDemo(page)
    await navegarMenu(page, { temaId: 'governanca', tituloLink: /^Relatórios SSRS$/ })
    await expect(page.getByTestId('route-relatorios')).toBeVisible({ timeout: 15000 })

    await assertVisualSnapshot(page, 'relatorios-painel', {
      locator: page.locator('.req-main'),
    })
  })
})
