const { test, expect } = require('@playwright/test')
const { mockResponsiveApis, loginDemo } = require('./helpers/responsiveMocks')

test('Painel de projetos apresenta a experiência Pulso separada das integrações', async ({ page }) => {
  await mockResponsiveApis(page)
  await loginDemo(page)

  await page.goto('/painel-projetos')

  await expect(page.getByTestId('route-painel-projetos')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Visão geral' })).toBeVisible()
  await expect(page.getByText('Panorama do portfólio')).toBeVisible()
  await expect(page.getByRole('img', { name: 'Distribuição da saúde dos projetos' })).toBeVisible()
  await expect(page.getByTestId('route-painel-integracao')).toHaveCount(0)
})
