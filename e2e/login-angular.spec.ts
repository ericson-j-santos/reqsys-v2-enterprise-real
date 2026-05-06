import { test, expect } from '@playwright/test'

test.describe('Login Angular', () => {
  test('login com credenciais válidas', async ({ page }) => {
    await page.goto('/login')
    expect(page.url()).toContain('login')

    await page.getByLabel('E-mail').fill('admin@reqsys.local')
    await page.getByLabel('Senha').fill('admin123')
    await page.getByRole('button', { name: /entrar/i }).click()

    await page.waitForURL('/', { timeout: 5000 })
    expect(page.url()).toBe('http://localhost:4200/')
  })

  test('exibe erro com credenciais inválidas', async ({ page }) => {
    await page.route('**/api/v1/auth/login', async route => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Credenciais inválidas' }),
      })
    })

    await page.goto('/login')

    await page.getByLabel('E-mail').fill('invalido@x.com')
    await page.getByLabel('Senha').fill('errado')
    await page.getByRole('button', { name: /entrar/i }).click()

    const errorMsg = page.getByText(/credenciais inválidas/i)
    await expect(errorMsg).toBeVisible({ timeout: 5000 })
    await expect(page).toHaveURL(/\/login$/)
  })

  test('preencher credenciais demo (Analista)', async ({ page }) => {
    await page.goto('/login')

    await page.getByRole('button', { name: 'Analista' }).click()

    await expect(page.getByLabel('E-mail')).toHaveValue('analista@reqsys.local')
    await expect(page.getByLabel('Senha')).toHaveValue('Analista@123')
  })

  test('preencher credenciais demo (Auditor)', async ({ page }) => {
    await page.goto('/login')

    await page.getByRole('button', { name: 'Auditor' }).click()

    await expect(page.getByLabel('E-mail')).toHaveValue('auditor@reqsys.local')
    await expect(page.getByLabel('Senha')).toHaveValue('Auditor@123')
  })
})
