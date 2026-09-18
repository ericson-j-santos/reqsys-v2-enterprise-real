const { test, expect } = require('@playwright/test')

async function habilitarLoginDemo(page) {
    await page.route('**/v1/auth/config', async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                data: {
                    azure_enabled: false,
                    certificate_enabled: false,
                    demo_login_enabled: true,
                    missing_fields: [],
                    expected_redirect_uri: '',
                    operator_action: '',
                },
            }),
        })
    })
}

test('login preserva ordem de foco por teclado entre e-mail e senha', async ({ page }) => {
    await habilitarLoginDemo(page)
    await page.goto('/login', { waitUntil: 'domcontentloaded' })

    const email = page.getByLabel(/e-?mail/i).first()
    const senha = page.getByLabel(/^Senha$/i).first()

    await expect(email).toBeVisible()
    await expect(senha).toBeVisible()

    await email.focus()
    await expect(email).toBeFocused()

    await page.keyboard.press('Tab')
    await expect(senha).toBeFocused()
})
