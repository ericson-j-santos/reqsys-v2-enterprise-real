const { test, expect } = require('@playwright/test')
const {
  mockResponsiveApis,
  loginDemo,
  hasMainHorizontalOverflow,
} = require('./helpers/responsiveMocks')

const ROTAS_RESPONSIVAS = [
  { path: '/login', testId: 'route-login', public: true },
  { path: '/', testId: 'route-dashboard' },
  { path: '/requisitos', testId: 'route-requisitos' },
  { path: '/rastreabilidade', testId: 'route-rastreabilidade' },
  { path: '/auditoria', testId: 'route-auditoria' },
  { path: '/pipeline', testId: 'route-pipeline' },
  { path: '/relatorios', testId: 'route-relatorios' },
  { path: '/segredos-status', testId: 'route-segredos-status' },
  { path: '/qualidade-ia', testId: 'route-qualidade-ia' },
  { path: '/recomendacoes-ia', testId: 'route-recomendacoes-ia' },
  { path: '/task-console', testId: 'route-task-console' },
  { path: '/specs', testId: 'route-specs' },
  { path: '/hub-lowcode', testId: 'route-hub-lowcode' },
  { path: '/painel-integracao', testId: 'route-painel-integracao' },
  { path: '/arquitetura', testId: 'route-arquitetura' },
  { path: '/govbi-ia', testId: 'route-govbi-ia' },
]

const VIEWPORTS = [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1366, height: 768 },
]

test.describe('responsividade padrão ouro — 16 rotas', () => {
  test.beforeEach(async ({ page }) => {
    await mockResponsiveApis(page)
  })

  for (const viewport of VIEWPORTS) {
    test(`rotas operacionais sem overflow horizontal em ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height })

      await page.goto('/login')
      await expect(page.getByTestId('route-login')).toBeVisible()
      await expect(page.getByText('ReqSys Enterprise')).toBeVisible()

      await loginDemo(page)

      for (const rota of ROTAS_RESPONSIVAS.filter((item) => !item.public)) {
        await page.goto(rota.path)
        await expect(page.getByTestId(rota.testId)).toBeVisible({ timeout: 15000 })
        expect(await hasMainHorizontalOverflow(page)).toBe(false)
      }
    })
  }

  test('menu mobile abre e navega sem deslocar conteúdo', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await loginDemo(page)

    await page.locator('button[aria-label="Abrir menu de navegação"]').click()
    const menuLink = page.locator('.req-drawer a[href="/requisitos"]').first()
    await expect(menuLink).toBeVisible()
    await menuLink.click()
    await expect(page).toHaveURL(/\/requisitos$/)
    await expect(page.getByTestId('route-requisitos')).toBeVisible()
    expect(await hasMainHorizontalOverflow(page)).toBe(false)
  })

  test('dashboard preserva cards críticos em mobile', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await loginDemo(page)

    await expect(page.getByTestId('metric-card-requisitos')).toBeVisible()
    await expect(page.getByTestId('dashboard-info-card')).toBeVisible()
    expect(await hasMainHorizontalOverflow(page)).toBe(false)
  })
})
