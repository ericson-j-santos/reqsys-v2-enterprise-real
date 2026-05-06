import { test, expect } from '@playwright/test'

test.describe('Login Vuetify', () => {
  test('login com credenciais válidas', async ({ page }) => {
    await page.route('**/api/v1/auth/login', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'e2e-token-admin',
          token_type: 'bearer',
          usuario: {
            id: 1,
            nome: 'Usuário Demo',
            email: 'admin@reqsys.local',
            papel: 'admin',
            permissoes: ['dashboard:read', 'relatorios:read', 'auditoria:read'],
          },
        }),
      })
    })

    await page.goto('/login')
    expect(page.url()).toContain('login')

    await page.getByLabel('E-mail').fill('admin@reqsys.local')
    await page.getByLabel(/^Senha$/, { exact: true }).fill('admin123')
    await page.getByRole('button', { name: /entrar/i }).click()

    await page.waitForURL('/', { timeout: 5000 })
    expect(page.url()).toBe('http://localhost:5174/')
  })

  test('exibe erro com credenciais inválidas', async ({ page }) => {
    await page.route('**/api/v1/auth/login', async route => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Credenciais inválidas.' }),
      })
    })

    await page.goto('/login')

    await page.getByLabel('E-mail').fill('invalido@x.com')
    await page.getByLabel(/^Senha$/, { exact: true }).fill('errado')
    await page.getByRole('button', { name: /entrar/i }).click()

    const errorMsg = page.getByText(/credenciais inválidas/i)
    await expect(errorMsg).toBeVisible({ timeout: 5000 })
    await expect(page).toHaveURL(/\/login$/)
  })

  test('preencher credenciais demo (Admin)', async ({ page }) => {
    await page.goto('/login')

    await page.getByText('Admin').click()

    await expect(page.getByLabel('E-mail')).toHaveValue('admin@reqsys.local')
    await expect(page.getByLabel(/^Senha$/, { exact: true })).toHaveValue('admin123')
  })
})
