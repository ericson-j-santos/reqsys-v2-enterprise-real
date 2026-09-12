const { test, expect } = require('@playwright/test')
const { login } = require('./helpers/auth')

test.describe('integridade de navegação', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('rotas de compatibilidade preservam a intenção funcional', async ({ page }) => {
    await page.goto('/requisitos/coleta')
    await expect(page).toHaveURL(/\/requisitos\?acao=novo(?:&|$)/)
    await expect(page.getByTestId('route-requisitos')).toBeVisible()
    await expect(page.getByText('Nova solicitação de requisito', { exact: true })).toBeVisible()

    await page.goto('/notificacoes')
    await expect(page).toHaveURL(/\/painel-integracao\/?$/)
    await expect(page.getByTestId('route-painel-integracao')).toBeVisible()
  })

  test('itens de qualidade e preparação ficam alcançáveis no subgrupo de refinamento', async ({ page }) => {
    await page.getByTestId('nav-tema-requisitos').click()
    await page.getByTestId('nav-subgrupo-pipeline').click()

    await expect(page.getByRole('link', { name: 'Qualidade IA' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Recomendações IA' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Preparar tarefas' })).toBeVisible()
  })
})
