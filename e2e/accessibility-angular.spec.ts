import { test, expect } from '@playwright/test'

test.describe('Acessibilidade Angular', () => {
  test('campos de login possuem nome acessível', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByLabel('E-mail')).toBeVisible()
    await expect(page.getByLabel('Senha')).toBeVisible()
  })

  test('tab navega de E-mail para Senha', async ({ page }) => {
    await page.goto('/login')

    const email = page.getByLabel('E-mail')
    const senha = page.getByLabel('Senha')

    await page.keyboard.press('Tab')
    await expect(email).toBeFocused()

    await page.keyboard.press('Tab')
    await expect(senha).toBeFocused()
  })
})
