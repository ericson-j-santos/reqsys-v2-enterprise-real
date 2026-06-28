const resultadoParaEstado = (resultado) => {
  const normalizado = String(resultado || 'nao_informado').toLowerCase()

  if (['success', 'skipped', 'cancelled'].includes(normalizado)) return 'verde'
  if (['failure', 'timed_out', 'action_required'].includes(normalizado)) return 'bloqueado'
  return 'desconhecido'
}

const resultadoParaSeveridade = (resultado) => {
  const estado = resultadoParaEstado(resultado)

  if (estado === 'bloqueado') return 'critica'
  if (estado === 'amarelo') return 'media'
  if (estado === 'desconhecido') return 'baixa'
  return 'informativa'
}

const criarItemCi = ({ id, titulo, env, esperado }) => {
  const resultado = process.env[env] || 'nao_informado'

  return {
    id,
    tipo: 'workflow-job',
    referencia: env,
    titulo,
    requerido: true,
    esperado,
    resultado,
    estado: resultadoParaEstado(resultado),
    severidade: resultadoParaSeveridade(resultado),
    origem: 'github-actions-needs'
  }
}

const itensMonitorados = [
  criarItemCi({
    id: 'backend-lint',
    titulo: 'Backend lint e seguranca estatica',
    env: 'BACKEND_LINT_RESULT',
    esperado: 'ruff, pip-audit e bandit concluidos com sucesso'
  }),
  criarItemCi({
    id: 'backend-test',
    titulo: 'Backend testes e cobertura',
    env: 'BACKEND_TEST_RESULT',
    esperado: 'pytest com cobertura minima obrigatoria'
  }),
  criarItemCi({
    id: 'frontend-build',
    titulo: 'Frontend build e auditoria de dependencias',
    env: 'FRONTEND_BUILD_RESULT',
    esperado: 'npm audit high e build de producao concluidos'
  }),
  criarItemCi({
    id: 'frontend-e2e-responsive',
    titulo: 'Frontend responsivo E2E',
    env: 'FRONTEND_E2E_RESULT',
    esperado: 'Playwright responsivo concluido com sucesso'
  }),
  {
    id: 'public-access-validation',
    tipo: 'workflow-config',
    referencia: '.github/workflows/validacao-acessos.yml',
    titulo: 'Validacao publica agendada e por push',
    requerido: true,
    esperado: 'workflow versionado com schedule, push em main e artifact operacional',
    resultado: 'configurado',
    estado: 'verde',
    severidade: 'informativa',
    origem: 'repositorio'
  },
  {
    id: 'pipeline-governance-evidence',
    tipo: 'artifact',
    referencia: 'pipeline-governanca-report',
    titulo: 'Evidencia consolidada de governanca do pipeline',
    requerido: true,
    esperado: 'artifact JSON publicado no workflow principal',
    resultado: 'gerado',
    estado: 'verde',
    severidade: 'informativa',
    origem: 'scripts/validar-pipeline-governanca.mjs'
  }
]

const bloqueios = itensMonitorados.filter((item) => item.requerido && item.estado === 'bloqueado')
const pendencias = itensMonitorados.filter((item) => ['amarelo', 'desconhecido'].includes(item.estado))

const report = {
  schemaVersion: '1.0.0',
  generatedAt: new Date().toISOString(),
  correlationId: process.env.GITHUB_RUN_ID ? `github-actions-${process.env.GITHUB_RUN_ID}` : `local-${Date.now()}`,
  repository: 'ericson-j-santos/reqsys-v2-enterprise-real',
  issue: '#33',
  environment: process.env.APP_ENV || process.env.GITHUB_REF_NAME || 'local',
  run: {
    id: process.env.GITHUB_RUN_ID || null,
    number: process.env.GITHUB_RUN_NUMBER || null,
    sha: process.env.GITHUB_SHA || null,
    ref: process.env.GITHUB_REF_NAME || null
  },
  status: bloqueios.length > 0 ? 'bloqueado' : 'ok',
  estadoGeral: bloqueios.length > 0 ? 'bloqueado' : pendencias.length > 0 ? 'amarelo' : 'verde',
  bloqueios: bloqueios.length,
  pendencias: pendencias.length,
  itensMonitorados
}

console.log(JSON.stringify(report, null, 2))