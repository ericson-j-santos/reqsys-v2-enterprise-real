const { test, expect } = require('@playwright/test')
const { login, navegarMenu } = require('./helpers/auth')

test('dashboard exibe cards padrão ouro, pipeline e informações do sistema', async ({ page }) => {
  await login(page)

  await expect(page.getByText('ReqSys · Trilha C · Dashboard Operacional')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Dashboard de Requisitos' })).toBeVisible()
  await expect(page.getByTestId('metric-card-requisitos')).toBeVisible()
  await expect(page.getByTestId('metric-card-em-analise')).toBeVisible()
  await expect(page.getByText('Informações do sistema', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Pipeline operacional', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Abrir analítico').first()).toBeVisible()

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByTestId('metric-card-requisitos')).toBeVisible()
  await expect(page.getByText('Informações do sistema', { exact: true }).first()).toBeVisible()
})

test('clique no card navega para analítico filtrado', async ({ page }) => {
  await login(page)

  await page.getByTestId('metric-card-requisitos').click()
  await expect(page).toHaveURL(/\/requisitos/)
})

test('clique em destino analítico navega para rota correta', async ({ page }) => {
  await login(page)

  await page.getByTestId('destino-analytics').click()
  await expect(page).toHaveURL(/\/analytics/)
})

test('pipeline operacional é clicável e navega', async ({ page }) => {
  await login(page)

  await page.getByTestId('pipeline-step-entrada').click()
  await expect(page).toHaveURL(/\/hub-lowcode/)
})

test('dashboard responsivo em 600px mantém layout funcional', async ({ page }) => {
  await page.setViewportSize({ width: 600, height: 900 })
  await login(page)

  await expect(page.getByTestId('metric-card-requisitos')).toBeVisible()
  await expect(page.getByText('Pipeline operacional', { exact: true }).first()).toBeVisible()
})

test('menu lateral de navegação está presente', async ({ page }) => {
  await login(page)

  await expect(page.getByTestId('nav-tema-operacao')).toBeVisible()
  await expect(page.getByTestId('nav-tema-governanca')).toBeVisible()

  await navegarMenu(page, { temaId: 'governanca', tituloLink: /^Relatórios SSRS$/ })
  await expect(page).toHaveURL(/\/relatorios/)

  await navegarMenu(page, { temaId: 'requisitos', tituloLink: /^Rastreabilidade$/ })
  await expect(page).toHaveURL(/\/rastreabilidade/)

  await navegarMenu(page, { temaId: 'governanca', tituloLink: /^Auditoria$/ })
  await expect(page).toHaveURL(/\/auditoria/)
})
