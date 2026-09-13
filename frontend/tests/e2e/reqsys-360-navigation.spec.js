const { test, expect } = require('@playwright/test')
const { mockResponsiveApis, loginDemo } = require('./helpers/responsiveMocks')

test.describe('ReqSys 360 — coerência de navegação e consolidação', () => {
  test.beforeEach(async ({ page }) => {
    await mockResponsiveApis(page)
    await loginDemo(page)
  })

  test('mantém deep links históricos funcionais e os consolida nas experiências canônicas', async ({ page }) => {
    await page.goto('/requisitos/coleta')
    await expect(page.getByTestId('route-requisitos')).toBeVisible()
    await expect(page).toHaveURL(/\/requisitos\?acao=novo$/)

    await page.goto('/notificacoes')
    await expect(page.getByTestId('route-painel-integracao')).toBeVisible()
    await expect(page).toHaveURL(/\/painel-integracao$/)
  })

  test('usa Monitoramento como fonte canônica dos detalhes operacionais', async ({ page }) => {
    await page.goto('/analytics')
    await expect(page.getByTestId('route-analytics')).toBeVisible()
    await expect(page.getByTestId('analytics-destinations')).toBeVisible()
    await expect(page.getByText('Malha Operacional Unificada')).toHaveCount(0)

    await page.getByRole('button', { name: /saúde operacional/i }).click()
    await expect(page).toHaveURL(/\/monitoramento-operacional$/)
    await expect(page.getByTestId('route-monitoramento-operacional')).toBeVisible()
  })

  test('divide Administração em grupos alcançáveis sem perder rotas', async ({ page }) => {
    await page.goto('/monitoramento-operacional')
    await expect(page.getByTestId('nav-subgrupo-operacao')).toBeVisible()

    await page.goto('/admin/session-management')
    await expect(page.getByTestId('nav-subgrupo-seguranca-governanca')).toBeVisible()

    await page.goto('/orquestrador-ia')
    await expect(page.getByTestId('nav-subgrupo-engenharia-ia')).toBeVisible()
  })

  test('controle negativo mantém rota desconhecida fora das experiências válidas', async ({ page }) => {
    await page.goto('/reqsys-360-rota-inexistente')
    await expect(page.getByTestId('route-requisitos')).toHaveCount(0)
    await expect(page.getByTestId('route-painel-integracao')).toHaveCount(0)
    await expect(page.getByTestId('route-analytics')).toHaveCount(0)
  })
})
