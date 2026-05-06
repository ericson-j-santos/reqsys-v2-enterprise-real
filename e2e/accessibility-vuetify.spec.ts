import { test, expect } from '@playwright/test'

test.describe('Acessibilidade Vuetify', () => {
  test('campos de login possuem nome acessível', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByLabel('E-mail')).toBeVisible()
    await expect(page.getByLabel(/^Senha$/, { exact: true })).toBeVisible()
  })

  test('botão Entrar possui nome acessível', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByRole('button', { name: /entrar/i })).toBeVisible()
  })
})
