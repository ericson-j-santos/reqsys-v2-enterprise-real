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

function envelope(payload) {
  return {
    success: true,
    data: payload,
    errors: [],
    meta: { correlation_id: 'corr-e2e-responsivo' },
  }
}

function json(body) {
  const payload = body && body.success !== undefined ? body : envelope(body)
  return {
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  }
}

const handlers = [
  { pattern: /\/api\/govbi\/health$/, body: { service: 'govbi-proxy', status: 'ok', timeout_seconds: 15 } },
  { pattern: /\/api\/govbi\/funcionamento$/, body: {
    executadoEm: '2026-06-29T12:00:00Z',
    total: 5,
    aprovados: 5,
    reprovados: 0,
    percentual: 100,
    completo: true,
    resultados: [],
  } },
  { pattern: /\/api\/govbi\/perguntas$/, body: {
    statusFluxo: 'CONCLUIDO',
    correlationId: 'corr-e2e-govbi',
    resultado: { colunas: ['mes', 'total'], linhas: [{ mes: '2024-01', total: 3 }] },
    explicacao: 'Mock E2E GovBI',
    mascaramentoAplicado: true,
    avisos: [],
    nivelSensibilidade: 'BAIXA',
    metrica: 'contagem_registros',
    dimensoes: ['mes'],
    filtros: {},
    sqlGerado: 'SELECT mes, COUNT(*) FROM propostas GROUP BY mes',
    requerAprovacao: false,
    aprovacaoId: null,
  } },
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
  { pattern: /\/api\/v1\/dashboard\/ia/, body: {
    amostras_total: 2,
    janela_dias: 30,
    metricas: {
      taxa_aceitacao: { valor: { taxa: 0.5, aceitas: 1, total: 2 } },
      eficacia_pos_correcao: { valor: { taxa: 1, positivas: 1, aplicadas: 1 } },
      calibracao: { valor: { brier_score: 0.12 } },
    },
  } },
  { pattern: /\/api\/v1\/incidentes\/\d+$/, body: {
    id: 1,
    titulo: 'Incidente E2E',
    resumo_contexto: 'Contexto demonstrativo para recomendações IA.',
    modulo: 'Plataforma',
    funcionalidade: 'CI/CD',
    severidade: 'alta',
    score_atual: 0.8,
  } },
  { pattern: /\/api\/v1\/incidentes/, body: [{
    id: 1,
    titulo: 'Incidente E2E',
    resumo_contexto: 'Contexto demonstrativo para recomendações IA.',
    modulo: 'Plataforma',
    funcionalidade: 'CI/CD',
    severidade: 'alta',
    score_atual: 0.8,
  }] },
  { pattern: /\/api\/v1\/recomendacoes\/\d+$/, body: {
    id: 1,
    id_incidente: 1,
    titulo: 'Recomendação E2E',
    tipo_recomendacao: 'hotfix',
    confianca_ia: 0.8,
    recomendacao: 'Aplicar hotfix com validação regressiva.',
    decisao: null,
    outcome: null,
  } },
  { pattern: /\/api\/v1\/recomendacoes/, body: [{
    id: 1,
    id_incidente: 1,
    titulo: 'Recomendação E2E',
    tipo_recomendacao: 'hotfix',
    confianca_ia: 0.8,
    recomendacao: 'Aplicar hotfix com validação regressiva.',
  }] },
  { pattern: /\/api\/v1\/ia\/gerar-recomendacao$/, body: {
    recomendacao: 'Executar hotfix com rollback documentado.',
    confianca_ia: 0.72,
    modelo: 'reqsys-heuristica-local',
  } },
  { pattern: /\/api\/v1\/auditoria\/eventos/, body: {
    dados: [{
      id: 1,
      acao: 'REQUISITO_CRIADO',
      entidade: 'requisito',
      usuario: 'analista@reqsys.local',
      correlation_id: 'corr-e2e-auditoria',
      criado_em: '2026-06-29T12:00:00Z',
    }],
    paginacao: { total: 1, limit: 50, offset: 0 },
  } },
  { pattern: /\/api\/v1\/integracoes\/figma-github\/status/, body: { items: [] } },
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
    cards: [{ id: 'runtime-status', title: 'Runtime Status', value: 'healthy', severity: 'healthy', drilldown: '/api/runtime/health' }],
    sections: [{ id: 'workflow-topology', items: [{ step: 'health', label: 'Runtime Health', status: 'healthy', href: '/api/runtime/health' }] }],
    observability_readiness: { observability_percent: 80, topology_coverage: 70, correlation_depth: 2, operational_traceability: 75 },
    correlation_analytics: { artifact_name: 'runtime-correlation-report.json', correlation_id: 'corr-e2e' },
  } },
  { pattern: /\/api\/connectors\/health$/, body: { conectores: [{ ambiente: 'dev', conector: 'repository_provider', capability: 'repository.read', status: 'ready', criticidade: 'high', acao_sugerida: 'OK' }] } },
  { pattern: /\/api\/v1\/estatisticas$/, body: {
    schema_version: '2.1.0',
    correlation_id: 'corr-e2e-responsivo',
    coletado_em: '2026-06-29T12:00:00Z',
    ambiente: 'e2e_responsivo',
    resumo: { total: 1, internos: 1, externos: 0, invalidos: 0, nao_medidos: 0 },
    indicadores: [{
      id: 'total-requisitos',
      nome: 'Total de requisitos',
      descricao: 'Quantidade total de requisitos cadastrados.',
      categoria: 'Requisitos',
      valorAtual: 5,
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
      evidencias: ['endpoint backend /v1/estatisticas'],
      pendencias: [],
    }],
  } },
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
