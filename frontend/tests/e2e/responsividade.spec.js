const { test, expect } = require('@playwright/test')

const usuarioAdmin = {
  email: 'analista@reqsys.local',
  nome: 'Analista ReqSys',
  papel: 'admin',
  permissoes: [
    'dashboard:read',
    'requisitos:write',
    'rastreabilidade:read',
    'auditoria:read',
    'relatorios:read',
  ],
}

async function mockApi(page) {
  await page.route('**/api/v1/auth/config', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: { azure_enabled: false, demo_login_enabled: true } }),
    })
  })

  await page.route('**/api/v1/auth/login', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          access_token: 'token-e2e-responsividade',
          token_type: 'bearer',
          usuario: usuarioAdmin,
        },
      }),
    })
  })

  await page.route('**/api/v1/dashboard/requisitos', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          total: 128,
          em_analise: 17,
          aprovados: 73,
          pendentes: 9,
        },
      }),
    })
  })

  await page.route('**/api/v1/dashboard/info', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          timestamp: '2026-06-18T21:00:00Z',
          resumo: {
            total_requisitos: 128,
            sistema_status: 'operacional',
            ambiente: 'e2e_responsivo',
          },
          endpoints_criticos: [
            { titulo: 'Health', metodo: 'GET', url: '/health' },
            { titulo: 'Dashboard', metodo: 'GET', url: '/v1/dashboard/info' },
          ],
        },
      }),
    })
  })

  await page.route('**/api/v1/qualidade-ia/resumo', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: { score_geral: 92 } }),
    })
  })
}

async function loginDemo(page) {
  await page.goto('/login')
  await expect(page.getByText('ReqSys Enterprise')).toBeVisible()
  await page.getByRole('button', { name: /entrar \(demo\)/i }).click()
  await expect(page.getByRole('heading', { name: /dashboard de requisitos/i })).toBeVisible()
}

async function expectMainWithoutHorizontalOverflow(page) {
  const hasOverflow = await page.locator('.req-main').evaluate((element) => element.scrollWidth > element.clientWidth + 2)
  expect(hasOverflow).toBe(false)
}

test.describe('responsividade do layout principal', () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page)
  })

  for (const viewport of [
    { name: 'mobile', width: 390, height: 844 },
    { name: 'tablet', width: 768, height: 1024 },
    { name: 'desktop', width: 1366, height: 768 },
  ]) {
    test(`dashboard sem overflow horizontal em ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height })
      await loginDemo(page)

      await expectMainWithoutHorizontalOverflow(page)
      await expect(page.getByTestId('metric-card-requisitos')).toBeVisible()
      await expect(page.getByTestId('dashboard-info-card')).toBeVisible()
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

    await expectMainWithoutHorizontalOverflow(page)
  })

  test('arquitetura viva navega e abre inspector sem overflow', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await loginDemo(page)

    await page.goto('/arquitetura-viva')
    await expect(page.getByRole('heading', { name: /arquitetura viva/i })).toBeVisible()
    await expect(page.getByTestId('architecture-live-canvas')).toBeVisible()

    await page.getByTestId('architecture-node-ci').click()
    await expect(page.getByTestId('architecture-live-inspector')).toContainText('CI/CD')

    await page.getByTestId('architecture-live-filter').fill('analytics')
    await expect(page.getByTestId('architecture-node-analytics')).toBeVisible()

    await expectMainWithoutHorizontalOverflow(page)
  })
})
