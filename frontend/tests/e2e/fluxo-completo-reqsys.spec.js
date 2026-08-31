const { test, expect } = require('@playwright/test')

async function autenticarOperador(page) {
  await page.addInitScript(() => {
    localStorage.setItem('reqsys_token', 'e2e-fluxo-completo-token')
    localStorage.setItem('reqsys_usuario', JSON.stringify({
      id: 'e2e-operador',
      nome: 'Operador E2E',
      email: 'operador-e2e@example.invalid',
      papel: 'admin',
      permissoes: ['requisitos:write', 'dashboard:read'],
    }))
  })
}

async function responderJson(route, data, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify({ data }),
  })
}

test('fluxo completo: recebe, valida, estrutura e publica requisito preservando correlação', async ({ page }) => {
  await autenticarOperador(page)

  const chamadas = []
  const registrar = (etapa, route) => {
    const request = route.request()
    chamadas.push({
      etapa,
      metodo: request.method(),
      payload: request.postDataJSON(),
      correlationId: request.headers()['x-correlation-id'],
    })
  }

  await page.route('**/api/v1/solicitacoes', async (route) => {
    registrar('solicitacao', route)
    await responderJson(route, {
      id: 501,
      codigo: 'SOL-E2E-501',
      status: 'recebido',
    }, 201)
  })

  await page.route('**/api/v1/requisitos/validar', async (route) => {
    registrar('validacao', route)
    await responderJson(route, {
      aprovado_para_triagem: true,
      alertas: [],
      score_qualidade: 100,
    })
  })

  await page.route('**/api/v1/requisitos/estruturar/501', async (route) => {
    registrar('estruturacao', route)
    await responderJson(route, {
      requisito_id: 'REQ-E2E-501',
      requisitos_funcionais: ['RF-E2E-001'],
      requisitos_nao_funcionais: ['RNF-E2E-001'],
      criterios_aceite: ['CA-E2E-001'],
    })
  })

  await page.route('**/api/v1/backlog/publicar-redmine/501', async (route) => {
    registrar('publicacao', route)
    await responderJson(route, {
      issue_principal_id: 9901,
      subtarefas: [{ id: 9902, subject: 'RF-E2E-001' }],
      github_imported_count: 0,
      redmine_published_count: 2,
    })
  })

  await page.goto('/pipeline')
  await expect(page.getByTestId('route-pipeline')).toBeVisible()
  await expect(page.getByRole('heading', { name: /Fluxo de Requisitos/i })).toBeVisible()

  await page.getByLabel(/Título \*/i).fill('Validar fluxo ponta a ponta do ReqSys')
  await page.getByLabel(/Descrição \*/i).fill(
    'Validar o encadeamento completo da solicitação até a publicação final com correlação preservada.',
  )
  await page.getByLabel(/^Área$/i).fill('Engenharia')
  await page.getByLabel(/^Sistema$/i).fill('ReqSys')
  await page.getByLabel(/^Solicitante$/i).fill('Teste E2E')

  const executar = page.getByRole('button', { name: 'Executar Fluxo' })
  await expect(executar).toBeEnabled()
  await executar.click()

  await expect(page.getByText('Fluxo executado com sucesso!')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('REQ-E2E-501')).toBeVisible()
  await expect(page.getByText('SOL-E2E-501')).toBeVisible()
  await expect(page.getByText(/issues\/9901/)).toBeVisible()

  expect(chamadas.map(({ etapa }) => etapa)).toEqual([
    'solicitacao',
    'validacao',
    'estruturacao',
    'publicacao',
  ])
  expect(chamadas.every(({ metodo }) => metodo === 'POST')).toBe(true)

  const correlationIds = new Set(chamadas.map(({ correlationId }) => correlationId))
  expect(correlationIds.size).toBe(1)
  expect([...correlationIds][0]).toBeTruthy()

  expect(chamadas[0].payload).toMatchObject({
    origem: 'email',
    titulo: 'Validar fluxo ponta a ponta do ReqSys',
    urgencia: 'media',
    area: 'Engenharia',
    sistema: 'ReqSys',
    solicitante: 'Teste E2E',
  })
  expect(chamadas[1].payload).toMatchObject(chamadas[0].payload)
  expect(chamadas[2].payload).toMatchObject(chamadas[0].payload)
  expect(chamadas[3].payload).toMatchObject({
    use_github_import: false,
  })
})
