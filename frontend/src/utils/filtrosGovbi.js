const STATUS_VALIDOS = new Set(['CONCLUIDO', 'MODO_DEGRADADO', 'PENDENTE_APROVACAO', 'ERRO'])
const FONTES_VALIDAS = new Set(['backend', 'fallback', 'proxy'])

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

export function normalizarFiltrosGovbi(query = {}) {
  const status = String(query.status ?? '').trim().toUpperCase()
  const fonte = normalizarTexto(query.fonte)
  const correlationId = String(query.correlation_id ?? query.correlationId ?? '').trim()
  const data = String(query.data ?? query.dia ?? '').trim()
  const busca = String(query.busca ?? query.q ?? '').trim()
  const fallback = String(query.fallback ?? '').trim().toLowerCase()

  return {
    status: STATUS_VALIDOS.has(status) ? status : '',
    fonte: FONTES_VALIDAS.has(fonte) ? fonte : '',
    correlation_id: correlationId,
    data: /^\d{4}-\d{2}-\d{2}$/.test(data) ? data : '',
    busca,
    fallback: fallback === 'true' || fallback === '1' ? 'true' : fallback === 'false' || fallback === '0' ? 'false' : '',
  }
}

export function possuiFiltroAtivo(filtros = {}) {
  const normalizados = normalizarFiltrosGovbi(filtros)
  return Boolean(
    normalizados.status
    || normalizados.fonte
    || normalizados.correlation_id
    || normalizados.data
    || normalizados.busca
    || normalizados.fallback,
  )
}

export function filtrarConsultasGovbi(itens = [], filtros = {}) {
  const filtrosNormalizados = normalizarFiltrosGovbi(filtros)
  const busca = normalizarTexto(filtrosNormalizados.busca)
  const correlationId = normalizarTexto(filtrosNormalizados.correlation_id)

  return itens.filter((item) => {
    const statusItem = String(item.statusFluxo ?? '').toUpperCase()
    const fonteItem = normalizarTexto(item.fonte)
    const dataItem = extrairData(item.consultadoEm)
    const fallbackItem = Boolean(item.fallback)

    const statusOk = !filtrosNormalizados.status || statusItem === filtrosNormalizados.status
    const fonteOk = !filtrosNormalizados.fonte || fonteItem === filtrosNormalizados.fonte
    const correlationOk = !correlationId || normalizarTexto(item.correlationId).includes(correlationId)
    const dataOk = !filtrosNormalizados.data || dataItem === filtrosNormalizados.data
    const fallbackOk = !filtrosNormalizados.fallback
      || (filtrosNormalizados.fallback === 'true' ? fallbackItem : !fallbackItem)

    const textoBusca = normalizarTexto([
      item.pergunta,
      item.statusFluxo,
      item.fonte,
      item.erro,
      item.correlationId,
      item.explicacao,
    ].join(' '))
    const buscaOk = !busca || textoBusca.includes(busca)

    return statusOk && fonteOk && correlationOk && dataOk && fallbackOk && buscaOk
  })
}

export function criarQueryFiltrosGovbi(filtros = {}) {
  const normalizados = normalizarFiltrosGovbi(filtros)
  return Object.fromEntries(
    Object.entries(normalizados).filter(([, valor]) => Boolean(String(valor ?? '').trim())),
  )
}

export function criarRegistroConsultaGovbi({
  pergunta,
  statusFluxo,
  fonte,
  latenciaMs,
  correlationId,
  erro = '',
  fallback = false,
  explicacao = '',
}) {
  return {
    id: correlationId || `govbi-${Date.now()}`,
    pergunta: String(pergunta ?? '').trim(),
    statusFluxo: statusFluxo || 'CONCLUIDO',
    fonte: fonte || 'backend',
    latenciaMs: Number(latenciaMs) || 0,
    correlationId: correlationId || '',
    erro: String(erro ?? ''),
    fallback: Boolean(fallback),
    explicacao: String(explicacao ?? ''),
    consultadoEm: new Date().toISOString(),
  }
}

export function contarConsultasGovbi(itens = []) {
  return itens.reduce((acc, item) => {
    const status = String(item.statusFluxo ?? '').toUpperCase()
    if (status === 'ERRO' || status === 'MODO_DEGRADADO') acc.erros += 1
    if (item.fallback) acc.fallback += 1
    if (status === 'CONCLUIDO' && !item.fallback) acc.sucesso += 1
    return acc
  }, { erros: 0, fallback: 0, sucesso: 0 })
}

export function calcularMetricasGovbi(itens = []) {
  const contagem = contarConsultasGovbi(itens)
  const latencias = itens
    .map((item) => Number(item.latenciaMs) || 0)
    .filter((valor) => valor > 0)
  const latenciaMediaMs = latencias.length
    ? Math.round(latencias.reduce((acc, valor) => acc + valor, 0) / latencias.length)
    : 0

  return {
    total: itens.length,
    sucesso: contagem.sucesso,
    erros: contagem.erros,
    fallback: contagem.fallback,
    latenciaMediaMs,
  }
}

export function exportarEvidenciaGovbi(itens = [], filtros = {}) {
  const filtrados = filtrarConsultasGovbi(itens, filtros)
  return JSON.stringify({
    exportadoEm: new Date().toISOString(),
    modulo: 'govbi-ia',
    filtros: criarQueryFiltrosGovbi(filtros),
    metricas: calcularMetricasGovbi(filtrados),
    consultas: filtrados.map((item) => ({
      pergunta: item.pergunta,
      statusFluxo: item.statusFluxo,
      fonte: item.fonte,
      latenciaMs: item.latenciaMs,
      correlationId: item.correlationId,
      fallback: item.fallback,
      erro: item.erro,
      explicacao: item.explicacao,
      consultadoEm: item.consultadoEm,
    })),
  }, null, 2)
}

export const GOVBI_HISTORICO_KEY = 'reqsys_govbi_historico'

export function carregarHistoricoGovbi(storage = sessionStorage) {
  try {
    const salvo = JSON.parse(storage.getItem(GOVBI_HISTORICO_KEY) || '[]')
    return Array.isArray(salvo) ? salvo : []
  } catch {
    return []
  }
}

export function salvarHistoricoGovbi(itens, storage = sessionStorage, limite = 50) {
  storage.setItem(GOVBI_HISTORICO_KEY, JSON.stringify(itens.slice(0, limite)))
}
