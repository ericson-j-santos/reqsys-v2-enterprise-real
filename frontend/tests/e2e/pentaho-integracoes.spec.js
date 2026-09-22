const { test, expect } = require('@playwright/test')

async function autenticar(page) {
  await page.addInitScript(() => {
    localStorage.setItem('reqsys_token', 'e2e-token')
    localStorage.setItem('reqsys_usuario', JSON.stringify({
      id: 'e2e-admin',
      nome: 'Administrador E2E',
      email: 'e2e@example.invalid',
      papel: 'admin',
      permissoes: ['dashboard:read'],
    }))
  })
}

async function responderJson(route, payload, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  })
}

test('painel Pentaho exibe lotes e reprocessa quarentena pela API governada', async ({ page }) => {
  await autenticar(page)
  let reprocessamentos = 0

  await page.route('**/api/integracoes/pentaho/dashboard**', async (route) => {
    await responderJson(route, {
      dataReferenciaUtc: '2026-08-29',
      contagens: { recebidos: 8, concluidos: 6, processando: 1, quarentena: 1 },
      processos: [
        { processo: 'PRODUTOS_DIARIOS', status: 'CONCLUIDO', ultimaExecucao: '2026-08-29T20:00:00Z', loteId: 'lote-ok' },
      ],
      lotesRecentes: [
        {
          loteId: 'lote-q',
          lote: '20260829-001',
          correlationId: 'corr-e2e',
          processo: 'PRODUTOS_DIARIOS',
          versaoEntrada: 1,
          dataReferencia: '2026-08-29',
          status: 'QUARENTENA',
          registrosRecebidos: 10,
          registrosAceitos: 9,
          registrosRejeitados: 1,
          tentativas: 1,
          erroCodigo: 'FALHA_PROCESSAMENTO_ADAPTADOR',
          erroMensagem: 'registro inválido',
          criadoEm: '2026-08-29T19:59:00Z',
          atualizadoEm: '2026-08-29T20:00:00Z',
          processadoEm: '2026-08-29T20:00:00Z',
        },
      ],
    })
  })

  await page.route('**/api/integracoes/pentaho/lotes/lote-q/reprocessar', async (route) => {
    reprocessamentos += 1
    expect(route.request().method()).toBe('POST')
    await responderJson(route, {
      loteId: 'lote-q',
      correlationId: 'corr-e2e',
      status: 'PENDENTE',
      duplicado: false,
      consulta: '/api/integracoes/pentaho/lotes/lote-q',
    }, 202)
  })

  await page.goto('/integracoes/pentaho')

  await expect(page.getByRole('heading', { name: 'Integrações > Pentaho' })).toBeVisible()
  const painel = page.getByTestId('route-integracoes-pentaho')
  await expect(painel.getByText('8').first()).toBeVisible()
  await expect(painel.getByText('PRODUTOS_DIARIOS').first()).toBeVisible()
  // escopado à seção da página (não ao body inteiro): evita colidir com o
  // tooltip de navegação "Acompanhar lotes, processamento, quarentena e
  // reprocessamento", que também contém a palavra e é teleportado para o
  // fim do DOM, tornando `.last()` sem escopo ambíguo/frágil.
  await expect(painel.getByText('Quarentena', { exact: true }).last()).toBeVisible()

  await page.getByRole('button', { name: 'Reprocessar' }).click()
  await expect.poll(() => reprocessamentos).toBe(1)
})

test('exibe a mensagem de erro do backend quando o carregamento do painel falha', async ({ page }) => {
  await autenticar(page)

  await page.route('**/api/integracoes/pentaho/dashboard**', async (route) => {
    await responderJson(route, { detail: 'Falha ao consultar lotes no banco' }, 500)
  })

  await page.goto('/integracoes/pentaho')

  await expect(page.getByText('Falha ao consultar lotes no banco')).toBeVisible()
})

test('exibe mensagem genérica quando o carregamento falha sem detail do backend (erro de rede)', async ({ page }) => {
  await autenticar(page)

  await page.route('**/api/integracoes/pentaho/dashboard**', (route) => route.abort('failed'))

  await page.goto('/integracoes/pentaho')

  await expect(page.getByText('Não foi possível carregar o painel de integrações Pentaho.')).toBeVisible()
})

test('exibe o erro do backend quando reprocessar um lote fora de quarentena é rejeitado (409)', async ({ page }) => {
  await autenticar(page)
  let chamadasDashboard = 0
  let chamadasReprocessar = 0

  await page.route('**/api/integracoes/pentaho/dashboard**', async (route) => {
    chamadasDashboard += 1
    await responderJson(route, {
      dataReferenciaUtc: '2026-09-04',
      contagens: { recebidos: 1, concluidos: 0, processando: 0, quarentena: 1 },
      processos: [],
      lotesRecentes: [
        {
          loteId: 'lote-409', lote: '20260904-001', correlationId: 'corr-409', processo: 'PRODUTOS_DIARIOS',
          versaoEntrada: 1, dataReferencia: '2026-09-04', status: 'QUARENTENA', registrosRecebidos: 1,
          registrosAceitos: 0, registrosRejeitados: 1, tentativas: 1, erroCodigo: 'FALHA_PROCESSAMENTO_ADAPTADOR',
          erroMensagem: 'erro', criadoEm: '2026-09-04T10:00:00Z', atualizadoEm: '2026-09-04T10:00:00Z', processadoEm: '2026-09-04T10:00:00Z',
        },
      ],
    })
  })

  await page.route('**/api/integracoes/pentaho/lotes/lote-409/reprocessar', async (route) => {
    chamadasReprocessar += 1
    await responderJson(route, { detail: 'Somente lotes em QUARENTENA podem ser reprocessados' }, 409)
  })

  await page.goto('/integracoes/pentaho')
  await page.getByRole('button', { name: 'Reprocessar' }).click()

  await expect(page.getByText('Somente lotes em QUARENTENA podem ser reprocessados')).toBeVisible()
  await expect.poll(() => chamadasReprocessar).toBe(1)
  // erro no reprocessamento não deve disparar um novo carregamento do painel
  expect(chamadasDashboard).toBe(1)
})

test('exibe estados vazios quando não há processos nem lotes', async ({ page }) => {
  await autenticar(page)

  await page.route('**/api/integracoes/pentaho/dashboard**', async (route) => {
    await responderJson(route, {
      dataReferenciaUtc: '2026-09-04',
      contagens: { recebidos: 0, concluidos: 0, processando: 0, quarentena: 0 },
      processos: [],
      lotesRecentes: [],
    })
  })

  await page.goto('/integracoes/pentaho')

  await expect(page.getByText('Nenhum processo recebido.')).toBeVisible()
  await expect(page.getByText('Nenhum lote disponível.')).toBeVisible()
})

test('renderiza um status não mapeado sem quebrar a tela', async ({ page }) => {
  await autenticar(page)

  await page.route('**/api/integracoes/pentaho/dashboard**', async (route) => {
    await responderJson(route, {
      dataReferenciaUtc: '2026-09-04',
      contagens: { recebidos: 1, concluidos: 0, processando: 0, quarentena: 0 },
      processos: [],
      lotesRecentes: [
        {
          loteId: 'lote-status-novo', lote: '20260904-002', correlationId: 'corr-status-novo', processo: 'PRODUTOS_DIARIOS',
          versaoEntrada: 1, dataReferencia: '2026-09-04', status: 'STATUS_AINDA_NAO_MAPEADO', registrosRecebidos: 1,
          registrosAceitos: 1, registrosRejeitados: 0, tentativas: 0, erroCodigo: null, erroMensagem: null,
          criadoEm: '2026-09-04T10:00:00Z', atualizadoEm: null, processadoEm: null,
        },
      ],
    })
  })

  await page.goto('/integracoes/pentaho')

  // a tela não deve quebrar (heading continua visível) e o status desconhecido
  // aparece em texto bruto em vez de travar num rótulo/cor obrigatórios
  await expect(page.getByRole('heading', { name: 'Integrações > Pentaho' })).toBeVisible()
  await expect(page.getByText('STATUS_AINDA_NAO_MAPEADO')).toBeVisible()
})

test('lote fora de quarentena não exibe o botão Reprocessar', async ({ page }) => {
  await autenticar(page)

  await page.route('**/api/integracoes/pentaho/dashboard**', async (route) => {
    await responderJson(route, {
      dataReferenciaUtc: '2026-09-04',
      contagens: { recebidos: 1, concluidos: 1, processando: 0, quarentena: 0 },
      processos: [],
      lotesRecentes: [
        {
          loteId: 'lote-concluido', lote: '20260904-003', correlationId: 'corr-concluido', processo: 'PRODUTOS_DIARIOS',
          versaoEntrada: 1, dataReferencia: '2026-09-04', status: 'CONCLUIDO', registrosRecebidos: 1,
          registrosAceitos: 1, registrosRejeitados: 0, tentativas: 1, erroCodigo: null, erroMensagem: null,
          criadoEm: '2026-09-04T10:00:00Z', atualizadoEm: '2026-09-04T10:00:00Z', processadoEm: '2026-09-04T10:00:00Z',
        },
      ],
    })
  })

  await page.goto('/integracoes/pentaho')

  await expect(page.getByRole('heading', { name: 'Integrações > Pentaho' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Reprocessar' })).toHaveCount(0)
})

test('botão Atualizar recarrega o painel manualmente', async ({ page }) => {
  await autenticar(page)
  let chamadasDashboard = 0

  await page.route('**/api/integracoes/pentaho/dashboard**', async (route) => {
    chamadasDashboard += 1
    await responderJson(route, {
      dataReferenciaUtc: '2026-09-04',
      contagens: { recebidos: chamadasDashboard, concluidos: 0, processando: 0, quarentena: 0 },
      processos: [],
      lotesRecentes: [],
    })
  })

  await page.goto('/integracoes/pentaho')
  await expect.poll(() => chamadasDashboard).toBe(1)

  await page.getByRole('button', { name: 'Atualizar' }).click()
  await expect.poll(() => chamadasDashboard).toBe(2)
})
