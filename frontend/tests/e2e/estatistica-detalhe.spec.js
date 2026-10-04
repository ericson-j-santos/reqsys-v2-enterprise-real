const { test, expect } = require('@playwright/test')
const {
  mockResponsiveApis,
  loginDemo,
  hasMainHorizontalOverflow,
} = require('./helpers/responsiveMocks')

const VIEWPORTS = [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1366, height: 768 },
]

test.describe('REQSYS#004.P1 — detalhe operacional do indicador', () => {
  test.beforeEach(async ({ page }) => {
    await mockResponsiveApis(page)
  })

  for (const viewport of VIEWPORTS) {
    test(`abre detalhe e preserva filtros em ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height })
      await loginDemo(page)

      await page.goto('/estatisticas?estado=adequado')
      await expect(page.getByTestId('route-estatisticas')).toBeVisible()
      await page.getByTestId('estatisticas-abrir-total-requisitos').click()

      await expect(page).toHaveURL(/\/estatisticas\/total-requisitos/)
      await expect(page.getByTestId('route-estatistica-detalhe')).toBeVisible()
      await expect(page.getByRole('heading', { name: 'Total de requisitos' })).toBeVisible()
      await expect(page.getByTestId('estatistica-detalhe-correlation-id')).toContainText('corr-e2e-responsivo')
      await expect(page.getByTestId('estatistica-score-pendente')).toBeVisible()
      expect(await hasMainHorizontalOverflow(page)).toBe(false)

      await page.getByTestId('estatistica-detalhe-voltar').click()
      await expect(page).toHaveURL(/\/estatisticas\?estado=adequado$/)
      await expect(page.getByTestId('route-estatisticas')).toBeVisible()
      expect(await hasMainHorizontalOverflow(page)).toBe(false)
    })
  }
})
