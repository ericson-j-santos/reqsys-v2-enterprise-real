const { test, expect } = require('@playwright/test')
const { mockResponsiveApis, loginDemo } = require('./helpers/responsiveMocks')

const ariSnapshot = {
  evidence_scope: 'repository_contract',
  correlation_id: 'corr-ari-e2e',
  health_score: 78,
  production_ready: false,
  draft_recomendado: true,
  runtime_sql_validation: { runtime_sql_ready: true, production_evidence: false },
  staging_validation: { staging_ready: false },
  readiness_matrix: [
    {
      capability: 'Homologação',
      estado: 'EVIDENCIA_AUSENTE',
      evidencia: 'Sem evidência externa completa.',
      gap: 'Executar validação externa governada.',
      bloqueia_producao: true,
    },
  ],
  validacoes: [
    {
      codigo: 'AI_GROUNDING',
      nome: 'IA governada com fonte e linhagem',
      status: 'block',
      score: 55,
      evidencia: 'Sem fonte externa atual.',
      acao_recomendada: 'Bloquear promoção.',
    },
  ],
  production_gaps: ['Executar validação externa governada.'],
  figma: { status: 'evidence_pending', ready: false, evidence: 'Sem artefato visual atual.' },
}

test.describe('inteligência operacional de indicadores', () => {
  test.beforeEach(async ({ page }) => {
    await mockResponsiveApis(page, [
      {
        pattern: /\/api\/analytics-runtime-intelligence\/snapshot$/,
        body: ariSnapshot,
      },
    ])
    await loginDemo(page)
    await page.goto('/analytics-runtime-intelligence')
    await expect(page.getByTestId('route-analytics-runtime-intelligence')).toBeVisible()
  })

  test('mantém produção bloqueada sem evidência externa', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Inteligência operacional de indicadores' })).toBeVisible()
    await expect(page.getByText('Evidência externa pendente.', { exact: false })).toBeVisible()
    await expect(page.getByText('Bloqueado', { exact: true })).toBeVisible()
    await expect(page.getByText('EVIDENCIA_AUSENTE', { exact: true })).toBeVisible()
  })

  test('permanece navegável em viewport móvel', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.reload()
    await expect(page.getByTestId('route-analytics-runtime-intelligence')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Atualizar' })).toBeVisible()
  })
})
