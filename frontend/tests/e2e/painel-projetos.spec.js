const { test, expect } = require('@playwright/test')
const { mockResponsiveApis, loginDemo } = require('./helpers/responsiveMocks')

test('Painel de projetos apresenta a experiência Pulso separada das integrações', async ({ page }) => {
  await mockResponsiveApis(page)
  await loginDemo(page)

  await page.goto('/painel-projetos')

  await expect(page.getByTestId('route-painel-projetos')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Visão geral' })).toBeVisible()
  await expect(page.getByText('Panorama do portfólio')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'portal-atual', exact: true })).toBeVisible()
  await expect(page.getByText('acme/portal-atual', { exact: true })).toBeVisible()
  await expect(page.getByText('Agile Execução · projeto atual')).toBeVisible()
  await expect(page.getByText('feat/pulso')).toBeVisible()
  await expect(page.getByTestId('route-painel-integracao')).toHaveCount(0)
})
