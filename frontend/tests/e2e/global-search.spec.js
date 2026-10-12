const { test, expect } = require('@playwright/test')
const { mockResponsiveApis, loginDemo } = require('./helpers/responsiveMocks')

test.beforeEach(async ({ page }) => {
  await mockResponsiveApis(page)
  await loginDemo(page)
})

test('lupa abre, encontra seção e navega no desktop', async ({ page }) => {
  await page.getByTestId('global-search-trigger-desktop').click()
  await expect(page.getByTestId('global-search-input')).toBeFocused()
  await page.getByTestId('global-search-input').fill('RASTREABILIDADE')
  const resultado = page.getByTestId('global-search-result').filter({
    has: page.getByText('Rastreabilidade', { exact: true }),
  })
  await expect(resultado).toHaveCount(1)
  await resultado.click()
  await expect(page).toHaveURL(/\/rastreabilidade\/?$/)
  await expect(page.getByTestId('global-search-dialog')).not.toBeVisible()
})

test('atalho Ctrl+K e Enter levam ao primeiro resultado', async ({ page }) => {
  await page.keyboard.press('Control+k')
  await page.getByTestId('global-search-input').fill('painel de projetos')
  await page.getByTestId('global-search-input').press('Enter')
  await expect(page).toHaveURL(/\/painel-projetos\/?$/)
  await expect(page.getByTestId('global-search-dialog')).not.toBeVisible()
})

test('perfil sem autorização não encontra áreas administrativas', async ({ page }) => {
  await mockResponsiveApis(page, [{
    pattern: /\/api\/v1\/auth\/login$/,
    body: {
      access_token: 'token-e2e',
      token_type: 'bearer',
      usuario: {
        nome: 'Pessoa com acesso limitado',
        email: 'limitado@reqsys.local',
        papel: 'user',
        permissoes: ['dashboard:read'],
      },
    },
  }])
  await loginDemo(page)
  await page.getByTestId('global-search-trigger-desktop').click()
  await page.getByTestId('global-search-input').fill('central operacional')
  await expect(page.getByTestId('global-search-empty')).toBeVisible()
})

test('lupa pode ser usada no cabeçalho do celular', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByTestId('global-search-trigger-mobile').click()
  await page.getByTestId('global-search-input').fill('qualidade ia')
  await expect(page.getByTestId('global-search-result').filter({
    has: page.getByText('Qualidade IA', { exact: true }),
  })).toBeVisible()
  await page.getByTestId('global-search-close').click()
  await expect(page.getByTestId('global-search-dialog')).not.toBeVisible()
})
