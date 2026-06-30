const { test, expect } = require('@playwright/test')
const { mockResponsiveApis, loginDemo, hasMainHorizontalOverflow } = require('./helpers/responsiveMocks')

const INDICADORES_MOCK = {
  schema_version: '2.1.0',
  correlation_id: 'corr-e2e-estatisticas',
  coletado_em: '2026-06-29T12:00:00Z',
  ambiente: 'e2e_responsivo',
  resumo: {
    total: 2,
    internos: 2,
    externos: 0,
    invalidos: 0,
    nao_medidos: 0,
    fontes_externas: { total: 0, autorizadas_validas: 0, expiradas: 0, mock_marcadas: 0, pendentes_auditoria: 0 },
  },
  indicadores: [
    {
      id: 'total-requisitos',
      nome: 'Total de requisitos',
      descricao: 'Quantidade total de requisitos cadastrados.',
      categoria: 'Requisitos',
      valorAtual: 12,
      unidade: 'itens',
      tendencia: 'estavel',
      estadoAtual: 'adequado',
      estadoAlvo: 'avancado',
      formula: 'count(requisitos.id)',
      fonte: {
        id: 'reqsys-db-requisitos',
        tipo: 'interna',
        nome: 'Banco operacional ReqSys',
        origem: 'backend-db:requisitos',
        coletadoEm: '2026-06-29T12:00:00Z',
        confiabilidade: 'alta',
        versaoConector: 'backend-v2',
      },
      evidencias: ['consulta SQLAlchemy sobre tabela requisitos', 'endpoint backend /v1/estatisticas'],
      pendencias: [],
    },
    {
      id: 'requisitos-com-bdd',
      nome: 'Requisitos com BDD',
      descricao: 'Percentual de requisitos com critérios BDD.',
      categoria: 'Requisitos',
      valorAtual: 42,
      unidade: '%',
      tendencia: 'subindo',
      estadoAtual: 'atencao',
      estadoAlvo: 'avancado',
      formula: 'requisitos com marcadores BDD / total de requisitos * 100',
      fonte: {
        id: 'reqsys-db-requisitos-bdd',
        tipo: 'interna',
        nome: 'Banco operacional ReqSys',
        origem: 'backend-db:requisitos.descricao',
        coletadoEm: '2026-06-29T12:00:00Z',
        confiabilidade: 'alta',
        versaoConector: 'backend-v2',
      },
      evidencias: ['marcadores BDD avaliados no backend'],
      pendencias: ['elevar cobertura BDD dos requisitos'],
    },
  ],
}

test.describe('estatísticas v2 — dados reais internos', () => {
  test.beforeEach(async ({ page }) => {
    await mockResponsiveApis(page)
    await page.route('**/api/v1/estatisticas', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: INDICADORES_MOCK }),
      })
    })
    await loginDemo(page)
  })

  for (const viewport of [
    { name: 'mobile', width: 390, height: 844 },
    { name: 'desktop', width: 1366, height: 768 },
  ]) {
    test(`rota /estatisticas renderiza indicadores reais em ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height })
      await page.goto('/estatisticas')

      await expect(page.getByTestId('route-estatisticas')).toBeVisible()
      await expect(page.getByText('Guard rails válidos')).toBeVisible()
      await expect(page.getByTestId('estatisticas-card-total')).toBeVisible()
      await expect(page.getByTestId('estatisticas-indicador-total-requisitos')).toBeVisible()
      await expect(page.getByTestId('estatisticas-indicador-requisitos-com-bdd')).toBeVisible()
      await expect(page.getByTestId('estatisticas-indicador-total-requisitos').getByText('count(requisitos.id)')).toBeVisible()
      expect(await hasMainHorizontalOverflow(page)).toBe(false)
    })
  }

  test('drilldown por card atualiza query string', async ({ page }) => {
    await page.goto('/estatisticas')
    await page.getByTestId('estatisticas-card-atencao').click()
    await expect(page).toHaveURL(/estado=atencao/)
    await expect(page.getByTestId('estatisticas-indicador-requisitos-com-bdd')).toBeVisible()
  })
})
