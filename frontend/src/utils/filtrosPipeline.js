const ETAPAS_VALIDAS = new Set(['normalizar', 'solicitacao', 'validar', 'estruturar', 'publicar'])
const STATUS_VALIDOS = new Set(['idle', 'running', 'ok', 'warn', 'error'])
const CATEGORIAS_VALIDAS = new Set(['erro', 'aviso', 'pipeline', 'ok'])

function normalizarTexto(valor) {
  return String(valor ?? '')
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

function extrairData(iso) {
  if (!iso) return ''
  const data = new Date(iso)
  if (Number.isNaN(data.getTime())) return ''
  return data.toISOString().slice(0, 10)
}

export function categoriaEtapaPipeline(step = {}) {
  if (step.status === 'error') return 'erro'
  if (step.status === 'warn') return 'aviso'
  if (step.key === 'publicar') return 'pipeline'
  return 'ok'
}

export function normalizarFiltrosPipeline(query = {}) {
  const etapa = normalizarTexto(query.etapa ?? query.step)
  const status = normalizarTexto(query.status)
  const categoria = normalizarTexto(query.categoria)
  const correlationId = String(query.correlation_id ?? query.correlationId ?? '').trim()
  const data = String(query.data ?? query.dia ?? '').trim()
  const busca = String(query.busca ?? query.q ?? '').trim()
  const duracaoMin = Number(query.duracao_min ?? query.duracaoMin ?? 0)

  return {
    etapa: ETAPAS_VALIDAS.has(etapa) ? etapa : '',
    status: STATUS_VALIDOS.has(status) ? status : '',
    categoria: CATEGORIAS_VALIDAS.has(categoria) ? categoria : '',
    correlation_id: correlationId,
    data: /^\d{4}-\d{2}-\d{2}$/.test(data) ? data : '',
    busca,
    duracao_min: Number.isFinite(duracaoMin) && duracaoMin > 0 ? duracaoMin : 0,
  }
}

export function possuiFiltroAtivo(filtros = {}) {
  const normalizados = normalizarFiltrosPipeline(filtros)
  return Boolean(
    normalizados.etapa
    || normalizados.status
    || normalizados.categoria
    || normalizados.correlation_id
    || normalizados.data
    || normalizados.busca
    || normalizados.duracao_min,
  )
}

export function achatarHistoricoPipeline(execucoes = []) {
  return execucoes.flatMap((execucao) => (execucao.etapas || []).map((etapa) => ({
    ...etapa,
    execucaoId: execucao.id,
    executadoEm: execucao.executadoEm,
    correlationId: execucao.correlationId,
    solicitante: execucao.solicitante,
    modoDemo: execucao.modoDemo,
    statusGeral: execucao.statusGeral,
    categoria: etapa.categoria || categoriaEtapaPipeline(etapa),
  })))
}

export function filtrarEtapasPipeline(itens = [], filtros = {}) {
  const filtrosNormalizados = normalizarFiltrosPipeline(filtros)
  const busca = normalizarTexto(filtrosNormalizados.busca)
  const correlationId = normalizarTexto(filtrosNormalizados.correlation_id)

  return itens.filter((item) => {
    const etapaItem = normalizarTexto(item.key)
    const statusItem = normalizarTexto(item.status)
    const categoriaItem = normalizarTexto(item.categoria || categoriaEtapaPipeline(item))
    const dataItem = extrairData(item.executadoEm)
    const duracao = Number(item.duration) || 0

    const etapaOk = !filtrosNormalizados.etapa || etapaItem === filtrosNormalizados.etapa
    const statusOk = !filtrosNormalizados.status || statusItem === filtrosNormalizados.status
    const categoriaOk = !filtrosNormalizados.categoria || categoriaItem === filtrosNormalizados.categoria
    const correlationOk = !correlationId || normalizarTexto(item.correlationId).includes(correlationId)
    const dataOk = !filtrosNormalizados.data || dataItem === filtrosNormalizados.data
    const duracaoOk = !filtrosNormalizados.duracao_min || duracao >= filtrosNormalizados.duracao_min

    const textoBusca = normalizarTexto([
      item.label,
      item.log,
      item.key,
      item.status,
      item.solicitante,
      item.correlationId,
    ].join(' '))
    const buscaOk = !busca || textoBusca.includes(busca)

    return etapaOk && statusOk && categoriaOk && correlationOk && dataOk && duracaoOk && buscaOk
  })
}

export function criarQueryFiltrosPipeline(filtros = {}) {
  const normalizados = normalizarFiltrosPipeline(filtros)
  const entries = Object.entries(normalizados).filter(([, valor]) => {
    if (typeof valor === 'number') return valor > 0
    return Boolean(String(valor ?? '').trim())
  })
  return Object.fromEntries(entries)
}

export function criarRegistroExecucaoPipeline({
  correlationId,
  steps,
  solicitante,
  modoDemo,
  statusGeral,
}) {
  return {
    id: correlationId || `pipeline-${Date.now()}`,
    executadoEm: new Date().toISOString(),
    correlationId: correlationId || '',
    solicitante: solicitante || 'Usuário interno',
    modoDemo: Boolean(modoDemo),
    statusGeral: statusGeral || 'CONCLUIDO',
    etapas: (steps || []).map((step) => ({
      key: step.key,
      label: step.label,
      status: step.status,
      duration: step.duration,
      log: step.log,
      categoria: categoriaEtapaPipeline(step),
    })),
  }
}

export function contarEtapasPipeline(itens = []) {
  return itens.reduce((acc, item) => {
    const status = normalizarTexto(item.status)
    if (status === 'error') acc.erros += 1
    if (status === 'warn') acc.avisos += 1
    if (status === 'ok') acc.ok += 1
    return acc
  }, { erros: 0, avisos: 0, ok: 0 })
}

export const PIPELINE_HISTORICO_KEY = 'reqsys_pipeline_historico'

export function carregarHistoricoPipeline(storage = sessionStorage) {
  try {
    const salvo = JSON.parse(storage.getItem(PIPELINE_HISTORICO_KEY) || '[]')
    return Array.isArray(salvo) ? salvo : []
  } catch {
    return []
  }
}

export function salvarHistoricoPipeline(itens, storage = sessionStorage, limite = 30) {
  storage.setItem(PIPELINE_HISTORICO_KEY, JSON.stringify(itens.slice(0, limite)))
}
