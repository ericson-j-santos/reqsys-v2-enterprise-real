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
  await expect(page.getByText('8').first()).toBeVisible()
  await expect(page.getByText('PRODUTOS_DIARIOS').first()).toBeVisible()
  await expect(page.getByText('Quarentena').last()).toBeVisible()

  await page.getByRole('button', { name: 'Reprocessar' }).click()
  await expect.poll(() => reprocessamentos).toBe(1)
})
