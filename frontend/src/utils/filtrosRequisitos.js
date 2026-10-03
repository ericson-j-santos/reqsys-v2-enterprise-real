const STATUS_VALIDOS = new Set(['recebido', 'em_analise', 'aprovado', 'rejeitado'])
const URGENCIAS_VALIDAS = new Set(['baixa', 'media', 'alta', 'critica'])

function normalizarTexto(valor) {
  return String(valor ?? '')
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

export function normalizarFiltrosRequisitos(query = {}) {
  const status = normalizarTexto(query.status)
  const urgencia = normalizarTexto(query.urgencia)
  const area = String(query.area ?? '').trim()
  const busca = String(query.busca ?? query.q ?? '').trim()

  return {
    status: STATUS_VALIDOS.has(status) ? status : '',
    urgencia: URGENCIAS_VALIDAS.has(urgencia) ? urgencia : '',
    area,
    busca,
  }
}

export function possuiFiltroAtivo(filtros = {}) {
  return Boolean(filtros.status || filtros.urgencia || filtros.area || filtros.busca)
}

export function filtrarRequisitos(itens = [], filtros = {}) {
  const filtrosNormalizados = normalizarFiltrosRequisitos(filtros)
  const busca = normalizarTexto(filtrosNormalizados.busca)
  const area = normalizarTexto(filtrosNormalizados.area)

  return itens.filter((item) => {
    const statusItem = normalizarTexto(item.status)
    const urgenciaItem = normalizarTexto(item.urgencia)
    const areaItem = normalizarTexto(item.area)

    const statusOk = !filtrosNormalizados.status || statusItem === filtrosNormalizados.status
    const urgenciaOk = !filtrosNormalizados.urgencia || urgenciaItem === filtrosNormalizados.urgencia
    const areaOk = !area || areaItem.includes(area)

    const textoBusca = normalizarTexto([
      item.codigo,
      item.titulo,
      item.descricao,
      item.area,
      item.sistema,
      item.solicitante,
      item.status,
      item.urgencia,
    ].join(' '))
    const buscaOk = !busca || textoBusca.includes(busca)

    return statusOk && urgenciaOk && areaOk && buscaOk
  })
}

export function criarQueryFiltrosRequisitos(filtros = {}) {
  const normalizados = normalizarFiltrosRequisitos(filtros)
  return Object.fromEntries(
    Object.entries(normalizados).filter(([, valor]) => Boolean(String(valor ?? '').trim())),
  )
}
