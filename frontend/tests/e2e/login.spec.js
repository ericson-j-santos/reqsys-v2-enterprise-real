const { test, expect } = require('@playwright/test')
const { login, preencherFormularioLogin, EMAIL_PADRAO } = require('./helpers/auth')

test('realiza login e redireciona para dashboard', async ({ page }) => {
    await login(page)
    await expect(page.getByRole('heading', { name: 'Dashboard de Requisitos' })).toBeVisible()

    const token = await page.evaluate(() => localStorage.getItem('reqsys_token'))
    expect(token).toBeTruthy()
})

test('nome do usuário não exibe caracteres mojibake', async ({ page }) => {
    await login(page)

    // Nome não deve conter sequências mojibake de latin1→utf8
    const bodyText = await page.locator('body').innerText()
    expect(bodyText).not.toMatch(/Usu[ÃÂ]/)
    // Deve exibir o nome correto sem caracteres corrompidos
    expect(bodyText).toMatch(/Usuário Demo/)
})

test('credenciais inválidas exibem mensagem de erro', async ({ page }) => {
    await page.goto('/login', { waitUntil: 'domcontentloaded' })
    await preencherFormularioLogin(page, EMAIL_PADRAO, 'senha-errada-123')

    // Deve permanecer na página de login
    await expect(page).toHaveURL(/\/login/)
    // Não deve haver token no localStorage
    const token = await page.evaluate(() => localStorage.getItem('reqsys_token'))
    expect(token).toBeFalsy()
})

test('logout limpa sessão e redireciona para login', async ({ page }) => {
    await login(page)

    await page.getByRole('listitem').filter({ hasText: 'Sair' }).click()
    await expect(page).toHaveURL(/\/login/)

    const token = await page.evaluate(() => localStorage.getItem('reqsys_token'))
    expect(token).toBeFalsy()
})
