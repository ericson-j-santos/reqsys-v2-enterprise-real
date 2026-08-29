const { test, expect } = require('@playwright/test')

async function autenticar(page, permissoes) {
  await page.addInitScript(({ permissoes }) => {
    localStorage.setItem('reqsys_token', 'e2e-token')
    localStorage.setItem('reqsys_usuario', JSON.stringify({
      id: 'e2e-admin',
      nome: 'Administrador E2E',
      email: 'e2e@example.invalid',
      papel: 'admin',
      permissoes,
    }))
  }, { permissoes })
}

async function responderJson(route, payload, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  })
}

test('console de merge valida PR e solicita merge assíncrono sem executar GitHub real', async ({ page }) => {
  await autenticar(page, ['auditoria:read'])

  const requisicoesMerge = []
  await page.route('**/api/v1/admin/github-merge/pull-requests/1392**', async (route) => {
    await responderJson(route, {
      data: {
        titulo: 'PR de validação E2E',
        estado: 'open',
        mergeavel: true,
        checks: { aprovados: 3, total: 3, bloqueadores: [] },
        branch_origem: 'feat/e2e',
        branch_destino: 'main',
        sha: 'abc123e2e',
      },
    })
  })
  await page.route('**/api/v1/admin/github-merge/merge-assincrono', async (route) => {
    requisicoesMerge.push(route.request().postDataJSON())
    await responderJson(route, {
      data: {
        operacao_id: 'merge-e2e-001',
        estado: 'aceita',
        correlation_id: 'e2e-merge-correlation',
      },
    })
  })

  const pagina = page.getByTestId('route-github-merge')
  await page.goto('/admin/github-merge')
  await expect(pagina).toBeVisible()

  await pagina.getByLabel('Número da Solicitação de integração').fill('1392')
  await pagina.getByRole('button', { name: 'Validar Solicitação de integração' }).click()

  await expect(pagina.getByText('PR de validação E2E')).toBeVisible()
  await expect(pagina.getByText('3/3')).toBeVisible()
  await expect(pagina.getByText('abc123e2e')).toBeVisible()

  await pagina.getByLabel(/Confirmo o repositório, a Solicitação de integração, o destino e o SHA/i).check()
  await pagina.getByRole('button', { name: 'Solicitar integração de alterações assíncrono' }).click()

  await expect(pagina.getByRole('status')).toContainText('Solicitação aceita')
  expect(requisicoesMerge).toHaveLength(1)
  expect(requisicoesMerge[0]).toMatchObject({
    repositorio: 'ericson-j-santos/reqsys-v2-enterprise-real',
    pull_request: 1392,
    sha_esperado: 'abc123e2e',
    metodo: 'squash',
    acao: 'default',
  })
})

test('políticas Teams executam dry-run das duas políticas sem fallback', async ({ page }) => {
  await autenticar(page, ['teams-recipient-policies:admin'])

  const probes = []
  await page.route('**/api/v1/teams-gateway/identity-status', async (route) => {
    await responderJson(route, {
      data: {
        configured: true,
        profile_name: 'teams-e2e',
        environment: 'dev',
        client_id_suffix: 'E2E1',
        rotation_due_at: '2026-12-31T12:00:00Z',
        rotation_required: false,
      },
    })
  })
  await page.route('**/api/v1/teams-gateway/recipient-policies/recipients**', async (route) => {
    const url = new URL(route.request().url())
    const politica = url.searchParams.get('politica')
    const item = politica === 'hitl-approvers'
      ? {
          id: 'hitl-e2e',
          politica,
          nome: 'Aprovadores E2E',
          destino_id: 'destino-hitl-e2e',
          destino_tipo: 'chat',
          prioridade: 100,
          ativo: true,
        }
      : {
          id: 'ops-e2e',
          politica,
          nome: 'Operação E2E',
          destino_id: 'destino-ops-e2e',
          destino_tipo: 'canal',
          prioridade: 100,
          ativo: true,
        }
    await responderJson(route, { data: { items: [item] } })
  })
  await page.route('**/api/v1/teams-gateway/recipient-policies/*/messages', async (route) => {
    const url = new URL(route.request().url())
    const politica = url.pathname.split('/').at(-2)
    const body = route.request().postDataJSON()
    probes.push({ politica, body })
    await responderJson(route, {
      data: {
        dry_run: true,
        entregue: true,
        fallback_usado: false,
        correlation_id: `e2e-${politica}`,
      },
    })
  })

  const pagina = page.getByTestId('route-teams-recipient-policies')
  await page.goto('/admin/teams-recipient-policies')
  await expect(pagina).toBeVisible()
  await expect(pagina.getByRole('heading', { name: 'Políticas de destinatários Teams' })).toBeVisible()
  await expect(page.getByTestId('teams-graph-identity-status')).toContainText('Ativa')

  await pagina.getByRole('button', { name: 'Executar dry-run das duas políticas' }).click()

  await expect(pagina.getByText(/2\/2 políticas READY\. Candidato/)).toBeVisible()
  await expect(pagina.getByRole('status')).toContainText('2/2 políticas READY')
  expect(probes).toHaveLength(2)
  expect(probes.map((item) => item.politica).sort()).toEqual(['hitl-approvers', 'reqsys-operations'])
  for (const probe of probes) {
    expect(probe.body).toMatchObject({
      dry_run: true,
      permitir_fallback: false,
      delivery_mode: 'first_success',
      modo: 'auto',
    })
  }
})

test('Agile Runtime carrega launchpad e cria branch por API controlada', async ({ page }) => {
  await autenticar(page, ['dashboard:read'])

  const criacoes = []
  const workItem = {
    id: 7,
    codigo: 'REQ-E2E-007',
    titulo: 'Provar launchpad governado',
    status: 'em_andamento',
    branch: 'feat/req-e2e-007',
    repositorio: 'ericson-j-santos/reqsys-v2-enterprise-real',
  }
  const launchpad = {
    branch_trabalho: 'feat/req-e2e-007',
    branch_base: 'main',
    repositorio: 'ericson-j-santos/reqsys-v2-enterprise-real',
    requisito_codigo: 'REQ-E2E-007',
    acoes_disponiveis: ['abrir_branch', 'abrir_pr', 'ver_actions', 'criar_branch_api'],
    links: {
      branch: 'https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/tree/feat/req-e2e-007',
      criar_branch: 'https://github.com/ericson-j-santos/reqsys-v2-enterprise-real',
      novo_pr: 'https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/compare/main...feat/req-e2e-007',
      actions: 'https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions',
      app_ambiente: null,
      change_request: null,
    },
    increment_gate: { permitido: true, detalhe: 'ok' },
    branch_existe: false,
    somente_leitura: false,
    mensagem_commit_sugerida: 'feat(e2e): validar launchpad',
  }

  await page.route('**/api/v1/agile-runtime/work-items', async (route) => {
    await responderJson(route, { data: [workItem] })
  })
  await page.route('**/api/v1/agile-runtime/work-items/7/github-launchpad**', async (route) => {
    await responderJson(route, { data: launchpad })
  })
  await page.route('**/api/v1/agile-runtime/work-items/7/github/branch', async (route) => {
    criacoes.push(route.request().postDataJSON())
    await responderJson(route, { data: { criada: true, branch: 'feat/req-e2e-007' } })
  })

  const pagina = page.getByTestId('route-agile-runtime')
  await page.goto('/agile-runtime')
  await expect(pagina).toBeVisible()
  await expect(pagina.getByRole('heading', { name: 'Integração com GitHub' })).toBeVisible()
  await expect(pagina.getByText('REQ-E2E-007').first()).toBeVisible()
  await expect(pagina.getByText('feat/req-e2e-007').first()).toBeVisible()

  await pagina.getByRole('button', { name: 'Criar versão de código pelo serviço' }).click()

  await expect(pagina.getByRole('status')).toContainText('Versão de código criada pelo GitHub.')
  expect(criacoes).toEqual([{
    ambiente: 'dev',
    criar_se_ausente: true,
    aplicar_branch_no_item: true,
  }])
})
