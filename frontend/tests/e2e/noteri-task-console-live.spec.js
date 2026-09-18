const { test, expect } = require('@playwright/test')

const usuario = {
  id: 'e2e-noteri-ui',
  nome: 'Validação local Noteri',
  email: 'noteri-ui-e2e@reqsys.local',
  papel: 'admin',
  permissoes: ['dashboard:read'],
}

async function prepararSessao(page) {
  await page.addInitScript((sessao) => {
    localStorage.setItem('reqsys_token', 'e2e-noteri-ui-token')
    localStorage.setItem('reqsys_usuario', JSON.stringify(sessao))
  }, usuario)

  await page.route('**/api/**', async (route) => {
    const url = route.request().url()
    if (url.includes('/v1/auth/config')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: { environment: 'test' } }),
      })
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: [] }),
    })
  })
}

async function lerPerfil(request) {
  const response = await request.get('http://127.0.0.1:8765/v1/profile')
  expect(response.ok()).toBeTruthy()
  return response.json()
}

async function restaurarNormal(request) {
  const correlationId = `noteri-ui-e2e-cleanup-${Date.now()}`
  const response = await request.post('http://127.0.0.1:8765/v1/profile', {
    data: {
      host: 'Noteri',
      profile: 'NORMAL',
      correlation_id: correlationId,
    },
  })
  expect(response.ok()).toBeTruthy()
  const observed = await lerPerfil(request)
  expect(observed.profile).toBe('NORMAL')
  expect(observed.accepts_new_development).toBe(true)
}

test('Task Console alterna Noteri por clique real e restaura NORMAL', async ({ page, request }, testInfo) => {
  await prepararSessao(page)

  try {
    await page.goto('/task-console')
    const route = page.getByTestId('route-task-console')
    const card = page.getByTestId('noteri-study-mode-card')
    const ativarEstudo = page.getByRole('button', { name: 'Ativar estudo' })
    const voltarDesenvolvimento = page.getByRole('button', { name: 'Voltar ao desenvolvimento' })

    await expect(route).toBeVisible()
    await expect(card).toContainText('NORMAL')
    await expect(ativarEstudo).toBeEnabled()

    const before = await lerPerfil(request)
    expect(before.profile).toBe('NORMAL')
    expect(before.accepts_new_development).toBe(true)

    await ativarEstudo.click()
    await expect(card).toContainText('ESTUDO')
    await expect(voltarDesenvolvimento).toBeEnabled()

    const study = await lerPerfil(request)
    expect(study.profile).toBe('ESTUDO')
    expect(study.accepts_new_development).toBe(false)
    await page.screenshot({ path: testInfo.outputPath('noteri-estudo.png'), fullPage: true })

    await voltarDesenvolvimento.click()
    await expect(card).toContainText('NORMAL')
    await expect(ativarEstudo).toBeEnabled()

    const normal = await lerPerfil(request)
    expect(normal.profile).toBe('NORMAL')
    expect(normal.accepts_new_development).toBe(true)
    await page.screenshot({ path: testInfo.outputPath('noteri-normal-final.png'), fullPage: true })
  } finally {
    await restaurarNormal(request)
  }
})
