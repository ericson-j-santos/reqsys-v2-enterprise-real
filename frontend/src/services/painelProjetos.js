const STATUS_PROGRESS = {
  recebido: 10, refinamento: 25, pronto_para_aprovacao: 40, aprovado: 50,
  em_execucao: 65, validado: 80, evidenciado: 90, exportado: 100,
  novo: 10, refinando: 25, pronto_para_sprint: 35, planejado: 45,
  em_revisao: 70, em_ci: 78, homologacao: 85, producao: 92,
  monitorado: 96, concluido: 100, bloqueado: 35,
}

export function projectHealth(status, ciStatus) {
  if (status === 'bloqueado' || ciStatus === 'failed') return 'Atrasado'
  if (['recebido', 'refinamento', 'novo', 'refinando'].includes(status)) return 'Em atenção'
  if (['exportado', 'concluido'].includes(status)) return 'Concluído'
  return 'No ritmo'
}

export function buildPulsoPortfolio(requisitos = [], workItems = [], traceRows = [], environment = 'DEV') {
  const workByRequirement = new Map(workItems.filter((item) => item.requisito_id).map((item) => [item.requisito_id, item]))
  const traceByRequirement = new Map(traceRows.map((item) => [item.requisito_id ?? item.id_requisito, item]))

  const projects = requisitos.map((req) => {
    const work = workByRequirement.get(req.id)
    const trace = traceByRequirement.get(req.id)
    const status = work?.status || req.status || 'recebido'
    const progress = STATUS_PROGRESS[status] ?? 0
    const evidenceUrl = work?.deploy_url || work?.ci_url || work?.change_url || trace?.evidencia_url || null
    return {
      id: `${environment}:${req.codigo || req.id}`,
      code: req.codigo || `REQ-${req.id}`,
      name: req.titulo || 'Projeto sem título',
      summary: req.descricao || '',
      owner: work?.owner_ai || req.solicitante || 'Não informado',
      solution: req.sistema || req.area || 'ReqSys',
      environment: (work?.ambiente_deploy && work.ambiente_deploy !== 'none' ? work.ambiente_deploy : environment).toUpperCase(),
      status,
      health: projectHealth(status, work?.ci_status),
      progress,
      nextMilestone: work?.ci_status === 'running' ? 'Integração contínua' : work?.deploy_status === 'deployed' ? 'Monitoramento' : 'Próxima transição',
      updatedAt: work?.atualizado_em || req.atualizado_em || null,
      origin: work ? 'ReqSys + Agile Execução' : 'ReqSys',
      plannerTaskId: trace?.planner_task_id || null,
      correlationId: trace?.correlation_id || null,
      evidenceUrl,
    }
  })

  const solutionMap = new Map()
  for (const project of projects) {
    const current = solutionMap.get(project.solution) || { name: project.solution, projects: 0, progress: 0, owner: project.owner }
    current.projects += 1
    current.progress += project.progress
    solutionMap.set(project.solution, current)
  }
  const solutions = [...solutionMap.values()].map((item) => ({ ...item, progress: Math.round(item.progress / item.projects) }))
  return { projects, solutions }
}
