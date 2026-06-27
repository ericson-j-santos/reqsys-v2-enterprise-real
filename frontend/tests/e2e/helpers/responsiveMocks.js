const usuarioAdmin = {
  email: 'analista@reqsys.local',
  nome: 'Analista ReqSys',
  papel: 'admin',
  permissoes: [
    'dashboard:read',
    'requisitos:write',
    'rastreabilidade:read',
    'auditoria:read',
    'relatorios:read',
  ],
}

function json(data) {
  return {
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ data }),
  }
}

const handlers = [
  { pattern: /\/api\/v1\/auth\/config$/, body: { azure_enabled: false, demo_login_enabled: true, environment: 'e2e_responsivo' } },
  { pattern: /\/api\/v1\/auth\/login$/, body: { access_token: 'token-e2e', token_type: 'bearer', usuario: usuarioAdmin } },
  { pattern: /\/api\/v1\/dashboard\/requisitos$/, body: { total: 12, em_analise: 3, aprovados: 7, pendentes: 2 } },
  { pattern: /\/api\/v1\/dashboard\/info$/, body: {
    timestamp: '2026-06-27T12:00:00Z',
    resumo: { total_requisitos: 12, sistema_status: 'operacional', ambiente: 'e2e_responsivo' },
    endpoints_criticos: [{ titulo: 'Health', metodo: 'GET', url: '/health' }],
  } },
  { pattern: /\/api\/v1\/qualidade-ia\/resumo/, body: { score_geral: 88, status: 'ok' } },
  { pattern: /\/api\/v1\/hub-lowcode\/integracoes\/historico/, body: { configurado: true, eventos: [], total: 0 } },
  { pattern: /\/api\/v1\/requisitos$/, body: [] },
  { pattern: /\/api\/v1\/relatorios\/ssrs\/health$/, body: { status: 'ok' } },
  { pattern: /\/api\/v1\/relatorios\/ssrs\/status$/, body: { online: true } },
  { pattern: /\/api\/v1\/relatorios\/ssrs$/, body: [] },
  { pattern: /\/api\/v1\/sistema\/segredos-status$/, body: { origem: 'env', total: 0, itens: [] } },
  { pattern: /\/api\/v1\/ia\/status$/, body: { status: 'ok' } },
  { pattern: /\/api\/v1\/dashboard\/ia/, body: { resumo: {}, series: [] } },
  { pattern: /\/api\/v1\/incidentes/, body: [] },
  { pattern: /\/api\/v1\/recomendacoes/, body: [] },
  { pattern: /\/api\/v1\/hub-lowcode\/status$/, body: { ambiente: { ambiente: 'dev', url_acesso: 'http://127.0.0.1:5173' } } },
  { pattern: /\/api\/v1\/hub-lowcode\/planner\/webhook-config$/, body: { teams_configurado: false, teams_webhook_url: '' } },
  { pattern: /\/api\/v1\/hub-lowcode\/pacotes$/, body: [] },
  { pattern: /\/api\/v1\/hub-lowcode\/flows$/, body: [] },
  { pattern: /\/api\/v1\/hub-lowcode\/github$/, body: { repos: [] } },
  { pattern: /\/api\/v1\/specs\/templates$/, body: [] },
  { pattern: /\/api\/v1\/specs$/, body: [] },
  { pattern: /\/api\/monitoramento-operacional$/, body: {
    schema_version: '1.0.0',
    resumo: { estado_geral: 'amarelo', bloqueios: 0, pendencias: 1, total_itens: 5 },
    itens: [{ tipo: 'gate', referencia: 'REQSYS-OPER-001', titulo: 'Gate CI', estado: 'amarelo', severidade: 'media' }],
  } },
  { pattern: /\/api\/runtime\/dashboard$/, body: {
    schema_version: '1.2.0',
    correlation_id: 'corr-e2e',
    cards: [{ id: 'runtime-status', title: 'Runtime Status', value: 'healthy', severity: 'healthy', drilldown: '/api/runtime/health', spa_drilldown: { path: '/monitoramento-operacional', query: { secao: 'runtime' } } }],
    sections: [
      { id: 'workflow-topology', items: [{ step: 'health', label: 'Runtime Health', status: 'healthy', href: '/api/runtime/health' }] },
      { id: 'incident-timeline', items: [] },
    ],
    observability_readiness: { observability_percent: 80, topology_coverage: 70, correlation_depth: 2, operational_traceability: 75 },
    correlation_analytics: { artifact_name: 'runtime-correlation-report.json', correlation_id: 'corr-e2e' },
  } },
  { pattern: /\/api\/runtime\/analytics$/, body: {
    schema_version: '1.4.0',
    correlation_id: 'corr-e2e',
    incident_lifecycle: { events: [] },
  } },
  { pattern: /\/api\/connectors\/health$/, body: { conectores: [{ ambiente: 'dev', conector: 'repository_provider', capability: 'repository.read', status: 'ready', criticidade: 'high', acao_sugerida: 'OK' }] } },
  { pattern: /\/api\/v1\/estatisticas$/, body: [] },
]

async function mockResponsiveApis(page) {
  await page.route('**/api/**', async (route) => {
    const url = route.request().url()
    const handler = handlers.find((item) => item.pattern.test(url))
    if (handler) {
      await route.fulfill(json(handler.body))
      return
    }
    await route.fulfill(json({}))
  })
}

async function loginDemo(page) {
  await page.goto('/login')
  await page.getByRole('button', { name: /entrar \(demo\)/i }).click()
  await page.waitForURL('**/')
}

async function hasMainHorizontalOverflow(page) {
  return page.locator('.req-main').evaluate((element) => element.scrollWidth > element.clientWidth + 2)
}

module.exports = {
  usuarioAdmin,
  mockResponsiveApis,
  loginDemo,
  hasMainHorizontalOverflow,
}
