const { test, expect } = require('@playwright/test')

const usuario = {
  nome: 'Usuário de validação UX',
  email: 'ux-smoke@reqsys.local',
  papel: 'admin',
  permissoes: [
    'dashboard:read',
    'requisitos:write',
    'rastreabilidade:read',
    'auditoria:read',
    'relatorios:read',
  ],
}

async function prepararSessao(page) {
  await page.addInitScript((sessao) => {
    localStorage.setItem('reqsys_token', 'ux-smoke-token')
    localStorage.setItem('reqsys_usuario', JSON.stringify(sessao))
  }, usuario)

  await page.route('**/api/**', async (route) => {
    const url = route.request().url()
    if (url.includes('/v1/auth/config')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: { environment: 'test' } }) })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: [] }) })
  })
}

test.describe('evidência UX global', () => {
  test.beforeEach(async ({ page }) => {
    await prepararSessao(page)
  })

  test('valida teclado, foco e anúncio de rota', async ({ page }, testInfo) => {
    await page.goto('/')
    const main = page.locator('#reqsys-main-content')
    await expect(main).toHaveAttribute('aria-label', 'Conteúdo principal')

    await page.keyboard.press('Tab')
    const skipLink = page.getByRole('link', { name: 'Ir para o conteúdo principal' })
    await expect(skipLink).toBeFocused()
    await expect(skipLink).toBeVisible()
    await skipLink.press('Enter')
    await expect(main).toBeFocused()

    await page.goto('/requisitos')
    await expect(page.locator('[data-testid="route-announcement"]')).toContainText('Navegação concluída')
    await expect(main).toBeFocused()

    await page.screenshot({ path: testInfo.outputPath('ux-desktop-keyboard-focus.png'), fullPage: true })
  })

  test('valida viewport móvel e menu acessível', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')

    const menu = page.getByRole('button', { name: 'Abrir menu de navegação' })
    await expect(menu).toBeVisible()
    await menu.click()
    await expect(page.locator('.req-drawer')).toBeVisible()
    await expect(page.locator('#reqsys-main-content')).toHaveAttribute('tabindex', '-1')

    await page.screenshot({ path: testInfo.outputPath('ux-mobile-navigation.png'), fullPage: true })
  })

  test('valida alerta offline e recuperação', async ({ page }, testInfo) => {
    await page.goto('/')
    await page.context().setOffline(true)
    await page.evaluate(() => window.dispatchEvent(new Event('offline')))
    await expect(page.locator('[data-testid="offline-alert"]')).toContainText('Conexão indisponível')
    await page.screenshot({ path: testInfo.outputPath('ux-offline-feedback.png'), fullPage: true })

    await page.context().setOffline(false)
    await page.evaluate(() => window.dispatchEvent(new Event('online')))
    await expect(page.locator('[data-testid="offline-alert"]')).toHaveCount(0)
  })
})
