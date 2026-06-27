const { test, expect } = require('@playwright/test')
const { login } = require('./helpers/auth')
const { mockResponsiveApis } = require('./helpers/responsiveMocks')

test.describe('Trilha C — UX Operacional padrão ouro', () => {
  test.beforeEach(async ({ page }) => {
    await mockResponsiveApis(page)
    await login(page)
  })

  test('hub analytics exibe semáforo, drilldown bar e cards clicáveis', async ({ page }) => {
    await page.goto('/analytics')
    await expect(page.getByTestId('route-analytics')).toBeVisible()
    await expect(page.getByTestId('operational-drilldown-bar')).toBeVisible()
    await expect(page.getByTestId('semaforo-verde').or(page.getByTestId('semaforo-amarelo')).or(page.getByTestId('semaforo-vermelho'))).toBeVisible()
    await expect(page.getByTestId('analytics-card-monitoramento')).toBeVisible()
    await page.getByTestId('analytics-card-monitoramento').click()
    await expect(page).toHaveURL(/\/monitoramento-operacional/)
  })

  test('monitoramento preserva filtros na URL via drill-down', async ({ page }) => {
    await page.goto('/monitoramento-operacional?estado=amarelo&secao=itens')
    await expect(page.getByTestId('route-monitoramento-operacional')).toBeVisible()
    await expect(page.getByTestId('operational-drilldown-bar')).toBeVisible()
    await expect(page.getByTestId('drilldown-filter-estado')).toBeVisible()
    await expect(page.getByTestId('drilldown-filter-secao')).toBeVisible()
    await page.getByTestId('monitoramento-card-bloqueios').click()
    await expect(page).toHaveURL(/estado=bloqueado/)
  })

  test('estatísticas aplica drill-down por card de resumo', async ({ page }) => {
    await page.goto('/estatisticas')
    await expect(page.getByTestId('route-estatisticas')).toBeVisible()
    await expect(page.getByTestId('operational-drilldown-bar')).toBeVisible()
    await page.getByTestId('estatisticas-card-criticos').click()
    await expect(page).toHaveURL(/estado=critico/)
  })

  test('incident timeline renderiza painel navegável', async ({ page }) => {
    await page.goto('/monitoramento-operacional')
    await expect(page.getByTestId('incident-timeline-panel')).toBeVisible()
    await expect(page.getByTestId('incident-timeline-empty').or(page.getByTestId('incident-timeline-item'))).toBeVisible()
  })

  test('layout responsivo em mobile mantém trilha C utilizável', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/analytics')
    await expect(page.getByTestId('route-analytics')).toBeVisible()
    await page.goto('/monitoramento-operacional')
    await expect(page.getByTestId('route-monitoramento-operacional')).toBeVisible()
    await page.goto('/estatisticas')
    await expect(page.getByTestId('route-estatisticas')).toBeVisible()
  })
})
