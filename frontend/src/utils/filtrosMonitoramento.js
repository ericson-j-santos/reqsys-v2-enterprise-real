const ESTADOS_VALIDOS = new Set(['verde', 'amarelo', 'vermelho', 'bloqueado', 'desconhecido'])
const SECOES_VALIDAS = new Set(['itens', 'conectores', 'runtime', 'metrics', 'timeline', 'ambientes'])
const SEVERIDADES_VALIDAS = new Set(['baixa', 'media', 'alta', 'critica', 'critical', 'high', 'medium', 'low'])

const SEMAFORO_MAP = {
  verde: { key: 'verde', label: 'Verde', color: 'green', icon: 'mdi-circle' },
  amarelo: { key: 'amarelo', label: 'Amarelo', color: 'amber', icon: 'mdi-circle' },
  vermelho: { key: 'vermelho', label: 'Vermelho', color: 'red', icon: 'mdi-circle' },
  bloqueado: { key: 'bloqueado', label: 'Bloqueado', color: 'red', icon: 'mdi-cancel' },
  desconhecido: { key: 'desconhecido', label: 'Desconhecido', color: 'grey', icon: 'mdi-help-circle-outline' },
  healthy: { key: 'verde', label: 'Verde', color: 'green', icon: 'mdi-circle' },
  runtime_healthy: { key: 'verde', label: 'Verde', color: 'green', icon: 'mdi-circle' },
  available: { key: 'verde', label: 'Verde', color: 'green', icon: 'mdi-circle' },
  attention: { key: 'amarelo', label: 'Amarelo', color: 'amber', icon: 'mdi-circle' },
  degraded: { key: 'vermelho', label: 'Vermelho', color: 'red', icon: 'mdi-circle' },
  runtime_degraded: { key: 'vermelho', label: 'Vermelho', color: 'red', icon: 'mdi-circle' },
  partial: { key: 'amarelo', label: 'Amarelo', color: 'amber', icon: 'mdi-circle' },
  unavailable: { key: 'vermelho', label: 'Vermelho', color: 'red', icon: 'mdi-circle' },
  critico: { key: 'vermelho', label: 'Crítico', color: 'red', icon: 'mdi-circle' },
  atencao: { key: 'amarelo', label: 'Atenção', color: 'amber', icon: 'mdi-circle' },
  adequado: { key: 'verde', label: 'Adequado', color: 'green', icon: 'mdi-circle' },
  avancado: { key: 'verde', label: 'Avançado', color: 'green', icon: 'mdi-circle' },
  nao_medido: { key: 'amarelo', label: 'Não medido', color: 'amber', icon: 'mdi-circle' },
  implemented: { key: 'verde', label: 'Implementado', color: 'green', icon: 'mdi-circle' },
  dry_run: { key: 'amarelo', label: 'Dry-run', color: 'amber', icon: 'mdi-circle' },
  green: { key: 'verde', label: 'Verde', color: 'green', icon: 'mdi-circle' },
  passed: { key: 'verde', label: 'Aprovado', color: 'green', icon: 'mdi-circle' },
  improving: { key: 'verde', label: 'Melhorando', color: 'green', icon: 'mdi-circle' },
  yellow: { key: 'amarelo', label: 'Amarelo', color: 'amber', icon: 'mdi-circle' },
  stable: { key: 'amarelo', label: 'Estável', color: 'amber', icon: 'mdi-circle' },
  failed: { key: 'vermelho', label: 'Falhou', color: 'red', icon: 'mdi-circle' },
  regressing: { key: 'vermelho', label: 'Regredindo', color: 'red', icon: 'mdi-circle' },
  ready: { key: 'verde', label: 'Pronto', color: 'green', icon: 'mdi-circle' },
  blocked: { key: 'vermelho', label: 'Bloqueado', color: 'red', icon: 'mdi-circle' },
  misconfigured: { key: 'vermelho', label: 'Misconfigurado', color: 'red', icon: 'mdi-circle' },
  missing_permission: { key: 'amarelo', label: 'Permissão ausente', color: 'amber', icon: 'mdi-circle' },
  insufficient_permission: { key: 'amarelo', label: 'Permissão insuficiente', color: 'amber', icon: 'mdi-circle' },
  expired: { key: 'amarelo', label: 'Expirado', color: 'amber', icon: 'mdi-circle' },
}

function normalizarTexto(valor) {
  return String(valor ?? '')
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

export function normalizarSemaforo(valor) {
  const chave = normalizarTexto(valor)
  return SEMAFORO_MAP[chave] || SEMAFORO_MAP.desconhecido
}

export function estadoParaSemaforo(estado) {
  return normalizarSemaforo(estado).key
}

export function normalizarFiltrosMonitoramento(query = {}) {
  const estado = normalizarTexto(query.estado)
  const secao = normalizarTexto(query.secao)
  const severidade = normalizarTexto(query.severidade)
  const correlationId = String(query.correlation_id ?? query.correlationId ?? '').trim()
  const busca = String(query.busca ?? query.q ?? '').trim()

  return {
    estado: ESTADOS_VALIDOS.has(estado) ? estado : '',
    secao: SECOES_VALIDAS.has(secao) ? secao : '',
    severidade: SEVERIDADES_VALIDAS.has(severidade) ? severidade : '',
    correlation_id: correlationId,
    busca,
  }
}

export function possuiFiltroMonitoramentoAtivo(filtros = {}) {
  const normalizados = normalizarFiltrosMonitoramento(filtros)
  return Boolean(
    normalizados.estado
    || normalizados.secao
    || normalizados.severidade
    || normalizados.correlation_id
    || normalizados.busca,
  )
}

export function criarQueryFiltrosMonitoramento(filtros = {}) {
  const normalizados = normalizarFiltrosMonitoramento(filtros)
  return Object.fromEntries(
    Object.entries(normalizados).filter(([, valor]) => Boolean(String(valor ?? '').trim())),
  )
}

export function filtrarItensMonitoramento(itens = [], filtros = {}) {
  const filtrosNormalizados = normalizarFiltrosMonitoramento(filtros)
  const busca = normalizarTexto(filtrosNormalizados.busca)
  const correlationId = normalizarTexto(filtrosNormalizados.correlation_id)
  const severidade = normalizarTexto(filtrosNormalizados.severidade)

  return itens.filter((item) => {
    const estadoItem = normalizarTexto(item.estado)
    const severidadeItem = normalizarTexto(item.severidade)
    const correlationItem = normalizarTexto(item.correlation_id)
    const estadoOk = !filtrosNormalizados.estado || estadoItem === filtrosNormalizados.estado
    const severidadeOk = !severidade || severidadeItem.includes(severidade)
    const correlationOk = !correlationId || correlationItem.includes(correlationId)
    const textoBusca = normalizarTexto([
      item.tipo,
      item.referencia,
      item.titulo,
      item.estado,
      item.severidade,
    ].join(' '))
    const buscaOk = !busca || textoBusca.includes(busca)
    return estadoOk && severidadeOk && correlationOk && buscaOk
  })
}

export function calcularResumoSemaforo(itens = []) {
  return itens.reduce((acc, item) => {
    const chave = estadoParaSemaforo(item.estado)
    acc[chave] = (acc[chave] || 0) + 1
    return acc
  }, { verde: 0, amarelo: 0, vermelho: 0, bloqueado: 0, desconhecido: 0 })
}

export function semaforoGeral(resumo = {}) {
  if ((resumo.bloqueado || 0) > 0 || (resumo.vermelho || 0) > 0) return 'vermelho'
  if ((resumo.amarelo || 0) > 0) return 'amarelo'
  if ((resumo.verde || 0) > 0) return 'verde'
  return 'desconhecido'
}
