const STATUS_PROGRESS = {
  recebido: 10, refinamento: 25, pronto_para_aprovacao: 40, aprovado: 50,
  em_execucao: 65, validado: 80, evidenciado: 90, exportado: 100,
  novo: 10, refinando: 25, pronto_para_sprint: 35, planejado: 45,
  em_revisao: 70, em_ci: 78, homologacao: 85, producao: 92,
  monitorado: 96, concluido: 100, bloqueado: 35,
}

const ACTIVE_STATUS_PRIORITY = [
  'bloqueado', 'em_ci', 'em_revisao', 'em_execucao', 'homologacao', 'producao',
  'monitorado', 'planejado', 'pronto_para_sprint', 'refinando', 'novo',
]

export function projectHealth(status, ciStatus) {
  if (status === 'bloqueado' || ciStatus === 'failed') return 'Atrasado'
  if (['recebido', 'refinamento', 'novo', 'refinando'].includes(status)) return 'Em atenção'
  if (['exportado', 'concluido'].includes(status)) return 'Concluído'
  return 'No ritmo'
}

function timestamp(value) {
  const parsed = value ? Date.parse(value) : Number.NaN
  return Number.isNaN(parsed) ? 0 : parsed
}

function currentStatus(items) {
  if (items.some((item) => item.status === 'bloqueado' || item.ci_status === 'failed')) return 'bloqueado'
  if (items.every((item) => ['concluido', 'exportado'].includes(item.status))) return 'concluido'
  return ACTIVE_STATUS_PRIORITY.find((status) => items.some((item) => item.status === status)) || items[0]?.status || 'novo'
}

function latestEvidence(items, traces) {
  for (const item of items) {
    const url = item.deploy_url || item.ci_url || item.change_url
    if (url) return url
  }
  return traces.find((trace) => trace.entrega_url || trace.change_url)?.entrega_url
    || traces.find((trace) => trace.change_url)?.change_url
    || null
}

function nextMilestone(items) {
  if (items.some((item) => item.status === 'bloqueado' || item.ci_status === 'failed')) return 'Remover impedimento'
  if (items.some((item) => item.ci_status === 'running' || item.status === 'em_ci')) return 'Integração contínua'
  if (items.some((item) => item.deploy_status === 'deployed' || item.status === 'monitorado')) return 'Monitoramento'
  if (items.every((item) => ['concluido', 'exportado'].includes(item.status))) return 'Concluído'
  return 'Próxima transição'
}

function repositoryKey(value) {
  return String(value || '').trim().toLocaleLowerCase('pt-BR')
}

/**
 * Constrói o portfólio a partir dos projetos reais referenciados pelos itens de
 * execução. Um projeto é um repositório explícito; requisitos sem repositório
 * não são promovidos artificialmente a projetos.
 */
export function buildPulsoPortfolio(requisitos = [], workItems = [], traceRows = [], environment = 'DEV') {
  const requirementById = new Map(requisitos.map((item) => [item.id, item]))
  const groups = new Map()

  for (const item of workItems) {
    const key = repositoryKey(item.repositorio)
    if (!key) continue
    const group = groups.get(key) || { repository: String(item.repositorio).trim(), items: [] }
    group.items.push(item)
    groups.set(key, group)
  }

  const projects = [...groups.values()].map(({ repository, items }) => {
    items.sort((a, b) => timestamp(b.atualizado_em) - timestamp(a.atualizado_em))
    const requirements = [...new Map(items
      .map((item) => requirementById.get(item.requisito_id))
      .filter(Boolean)
      .map((item) => [item.id, item])).values()]
    const requirementCodes = new Set(requirements.map((item) => item.codigo))
    const traces = traceRows.filter((trace) =>
      repositoryKey(trace.repositorio) === repositoryKey(repository)
      || requirementCodes.has(trace.requisito),
    )
    const status = currentStatus(items)
    const ciStatus = items.some((item) => item.ci_status === 'failed') ? 'failed' : items[0]?.ci_status
    const progress = Math.round(items.reduce((sum, item) => sum + (STATUS_PROGRESS[item.status] ?? 0), 0) / items.length)
    const systems = [...new Set(requirements.map((item) => item.sistema || item.area).filter(Boolean))]
    const environmentFromRuntime = items.find((item) => item.ambiente_deploy && item.ambiente_deploy !== 'none')?.ambiente_deploy
    const trace = traces[0]
    const change = items.find((item) => item.change_id || item.change_url)
    const name = repository.split('/').filter(Boolean).at(-1) || repository

    return {
      id: `repo:${repositoryKey(repository)}`,
      code: repository,
      name,
      summary: requirements[0]?.descricao || items[0]?.descricao || '',
      owner: items.find((item) => item.owner_ai)?.owner_ai || requirements[0]?.solicitante || 'Não informado',
      solution: systems.join(', ') || name,
      environment: String(environmentFromRuntime || trace?.ambiente || environment).toUpperCase(),
      status,
      health: projectHealth(status, ciStatus),
      progress,
      nextMilestone: nextMilestone(items),
      updatedAt: items[0]?.atualizado_em || trace?.criado_em || null,
      origin: 'Agile Execução · projeto atual',
      plannerTaskId: trace?.planner && trace.planner !== '—' ? trace.planner : null,
      correlationId: trace?.correlation_id || null,
      evidenceUrl: latestEvidence(items, traces),
      changeId: change?.change_id || trace?.entrega || null,
      branch: items.find((item) => item.branch)?.branch || null,
      workItems: items.length,
      requirements: requirements.length,
    }
  }).sort((a, b) => timestamp(b.updatedAt) - timestamp(a.updatedAt))

  const solutionMap = new Map()
  for (const project of projects) {
    const current = solutionMap.get(project.solution) || { name: project.solution, projects: 0, progress: 0, owner: project.owner }
    current.projects += 1
    current.progress += project.progress
    solutionMap.set(project.solution, current)
  }
  const solutions = [...solutionMap.values()].map((item) => ({ ...item, progress: Math.round(item.progress / item.projects) }))
  return {
    projects,
    solutions,
    unlinkedWorkItems: workItems.filter((item) => !repositoryKey(item.repositorio)).length,
  }
}
