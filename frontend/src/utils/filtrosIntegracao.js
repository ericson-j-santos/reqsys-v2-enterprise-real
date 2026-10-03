const TIPOS_VALIDOS = new Set(['planner', 'teams'])
const STATUS_VALIDOS = new Set(['sucesso', 'erro'])

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

export function normalizarFiltrosIntegracao(query = {}) {
  const tipo = normalizarTexto(query.tipo ?? query.origem)
  const status = normalizarTexto(query.status)
  const autor = String(query.autor ?? '').trim()
  const correlationId = String(query.correlation_id ?? query.correlationId ?? '').trim()
  const data = String(query.data ?? query.dia ?? '').trim()
  const busca = String(query.busca ?? query.q ?? '').trim()

  return {
    tipo: TIPOS_VALIDOS.has(tipo) ? tipo : '',
    status: STATUS_VALIDOS.has(status) ? status : '',
    autor,
    correlation_id: correlationId,
    data: /^\d{4}-\d{2}-\d{2}$/.test(data) ? data : '',
    busca,
  }
}

export function possuiFiltroAtivo(filtros = {}) {
  const normalizados = normalizarFiltrosIntegracao(filtros)
  return Boolean(
    normalizados.tipo
    || normalizados.status
    || normalizados.autor
    || normalizados.correlation_id
    || normalizados.data
    || normalizados.busca,
  )
}

export function filtrarIntegracoes(itens = [], filtros = {}) {
  const filtrosNormalizados = normalizarFiltrosIntegracao(filtros)
  const busca = normalizarTexto(filtrosNormalizados.busca)
  const autor = normalizarTexto(filtrosNormalizados.autor)
  const correlationId = normalizarTexto(filtrosNormalizados.correlation_id)

  return itens.filter((item) => {
    const tipoItem = normalizarTexto(item.tipo)
    const statusItem = normalizarTexto(item.status)
    const autorItem = normalizarTexto(item.autor)
    const correlationItem = normalizarTexto(item.correlation_id)
    const dataItem = extrairData(item.criado_em)

    const tipoOk = !filtrosNormalizados.tipo || tipoItem === filtrosNormalizados.tipo
    const statusOk = !filtrosNormalizados.status || statusItem === filtrosNormalizados.status
    const autorOk = !autor || autorItem.includes(autor)
    const correlationOk = !correlationId || correlationItem.includes(correlationId)
    const dataOk = !filtrosNormalizados.data || dataItem === filtrosNormalizados.data

    const textoBusca = normalizarTexto([
      item.titulo,
      item.mensagem,
      item.autor,
      item.tipo,
      item.status,
      item.correlation_id,
    ].join(' '))
    const buscaOk = !busca || textoBusca.includes(busca)

    return tipoOk && statusOk && autorOk && correlationOk && dataOk && buscaOk
  })
}

export function criarQueryFiltrosIntegracao(filtros = {}) {
  const normalizados = normalizarFiltrosIntegracao(filtros)
  return Object.fromEntries(
    Object.entries(normalizados).filter(([, valor]) => Boolean(String(valor ?? '').trim())),
  )
}

export function contarIntegracoesPorStatus(itens = []) {
  return itens.reduce((acc, item) => {
    const status = normalizarTexto(item.status)
    if (status === 'erro') acc.erros += 1
    if (status === 'sucesso') acc.sucessos += 1
    return acc
  }, { erros: 0, sucessos: 0 })
}
