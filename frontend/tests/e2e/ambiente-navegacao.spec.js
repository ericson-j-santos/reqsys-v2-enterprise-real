const { test, expect } = require('@playwright/test')
const { mockResponsiveApis, loginDemo } = require('./helpers/responsiveMocks')
const {
  instalarStubNavegacaoAmbiente,
  lerNavegacoesAmbiente,
  abrirMenuAmbienteDrawer,
  selecionarAmbienteNoMenu,
} = require('./helpers/ambienteNavigator')

test.describe('seletor de ambiente operacional', () => {
  test.beforeEach(async ({ page }) => {
    await mockResponsiveApis(page)
    await instalarStubNavegacaoAmbiente(page)
    await page.setViewportSize({ width: 1366, height: 768 })
    await loginDemo(page)
  })

  test('menu lateral lista ambientes navegáveis', async ({ page }) => {
    await abrirMenuAmbienteDrawer(page)

    await expect(page.getByTestId('ambiente-opcao-local')).toBeVisible()
    await expect(page.getByTestId('ambiente-opcao-dev')).toBeVisible()
    await expect(page.getByTestId('ambiente-opcao-stg')).toBeVisible()
    await expect(page.getByTestId('ambiente-opcao-prod')).toBeVisible()
    await expect(page.getByTestId('ambiente-opcao-prod')).toContainText(/Requer confirmação/i)
  })

  test('homolog navega preservando rota atual', async ({ page }) => {
    await page.goto('/monitoramento-operacional')
    await abrirMenuAmbienteDrawer(page)
    await selecionarAmbienteNoMenu(page, 'stg')

    const urls = await lerNavegacoesAmbiente(page)
    expect(urls).toEqual(['https://reqsys-app-stg.fly.dev/monitoramento-operacional'])
  })

  test('prod abre diálogo e cancelar não navega', async ({ page }) => {
    await abrirMenuAmbienteDrawer(page)
    await selecionarAmbienteNoMenu(page, 'prod')

    await expect(page.getByTestId('confirmacao-ambiente-prod-dialog')).toBeVisible()
    await expect(page.getByText('Abrir produção?')).toBeVisible()

    await page.getByTestId('confirmacao-ambiente-prod-cancelar').click()
    await expect(page.getByTestId('confirmacao-ambiente-prod-dialog')).not.toBeVisible()
    expect(await lerNavegacoesAmbiente(page)).toEqual([])
  })

  test('confirmar prod dispara navegação para URL canônica', async ({ page }) => {
    await abrirMenuAmbienteDrawer(page)
    await selecionarAmbienteNoMenu(page, 'prod')
    await page.getByTestId('confirmacao-ambiente-prod-confirmar').click()

    const urls = await lerNavegacoesAmbiente(page)
    expect(urls[0]).toMatch(/^https:\/\/reqsys-app\.fly\.dev\//)
  })

  test('dashboard exibe chip de ambiente clicável', async ({ page }) => {
    await expect(page.getByTestId('ambiente-chip')).toBeVisible()
    await page.getByTestId('ambiente-chip').click()
    await expect(page.getByTestId('ambiente-navigator-menu')).toBeVisible()
  })

  test('governança — linha homolog navega para instância staging', async ({ page }) => {
    await page.goto('/governanca')
    await page.getByRole('tab', { name: 'Ambientes' }).click()
    await page.getByTestId('ambiente-linha-stg').click()

    const urls = await lerNavegacoesAmbiente(page)
    expect(urls).toEqual(['https://reqsys-app-stg.fly.dev/governanca'])
  })

  test('governança — linha prod exige confirmação', async ({ page }) => {
    await page.goto('/governanca')
    await page.getByRole('tab', { name: 'Ambientes' }).click()
    await page.getByTestId('ambiente-linha-prod').click()

    await expect(page.getByTestId('confirmacao-ambiente-prod-dialog')).toBeVisible()
    await page.getByTestId('confirmacao-ambiente-prod-cancelar').click()
    expect(await lerNavegacoesAmbiente(page)).toEqual([])
  })

  test('arquitetura — confirmar prod navega para rota da página', async ({ page }) => {
    await page.goto('/arquitetura')
    await page.getByTestId('ambiente-linha-prod').click()
    await page.getByTestId('confirmacao-ambiente-prod-confirmar').click()

    const urls = await lerNavegacoesAmbiente(page)
    expect(urls).toEqual(['https://reqsys-app.fly.dev/arquitetura'])
  })
})
