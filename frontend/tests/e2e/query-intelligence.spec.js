const { test, expect } = require('@playwright/test')
const { mockResponsiveApis, loginDemo } = require('./helpers/responsiveMocks')

test.describe('análise inteligente de consultas', () => {
  test.beforeEach(async ({ page }) => {
    await mockResponsiveApis(page)
    await loginDemo(page)
    await page.goto('/query-intelligence')
    await expect(page.getByTestId('route-query-intelligence')).toBeVisible()
  })

  test('analisa consulta de leitura sem executar SQL', async ({ page }) => {
    const input = page.getByTestId('query-sql-input').locator('textarea')
    await input.fill('SELECT id, nome FROM clientes WHERE ativo = true')
    await page.getByRole('button', { name: 'Analisar' }).click()

    await expect(page.getByText('consulta dados de clientes', { exact: false })).toBeVisible()
    await expect(page.getByText('Comando potencialmente destrutivo', { exact: false })).toHaveCount(0)
  })

  test('sinaliza comando destrutivo como risco', async ({ page }) => {
    const input = page.getByTestId('query-sql-input').locator('textarea')
    await input.fill('DELETE FROM clientes WHERE id = 1')
    await page.getByRole('button', { name: 'Analisar' }).click()

    await expect(page.getByText('Comando potencialmente destrutivo detectado.', { exact: false })).toBeVisible()
    await expect(page.getByTestId('query-risk-chip')).toContainText('Risco')
  })
})
