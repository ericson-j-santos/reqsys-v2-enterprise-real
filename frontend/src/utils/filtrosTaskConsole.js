const STATUS_TAREFA_VALIDOS = new Set(['pendente', 'criada', 'falha'])
const PRIORIDADES_VALIDAS = new Set(['alta', 'media', 'baixa'])
const STATUS_ENVIO_VALIDOS = new Set(['sucesso', 'erro', 'parcial'])

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

export function normalizarFiltrosTaskConsole(query = {}) {
  const status = normalizarTexto(query.status)
  const bucket = String(query.bucket ?? '').trim()
  const prioridade = normalizarTexto(query.prioridade)
  const responsavel = String(query.responsavel ?? query.autor ?? '').trim()
  const busca = String(query.busca ?? query.q ?? '').trim()

  return {
    status: STATUS_TAREFA_VALIDOS.has(status) ? status : '',
    bucket,
    prioridade: PRIORIDADES_VALIDAS.has(prioridade) ? prioridade : '',
    responsavel,
    busca,
  }
}

export function normalizarFiltrosEnvioTaskConsole(query = {}) {
  const status = normalizarTexto(query.envio_status ?? query.status_envio)
  const correlationId = String(query.correlation_id ?? query.correlationId ?? '').trim()
  const data = String(query.data ?? query.dia ?? '').trim()
  const busca = String(query.busca_envio ?? query.q ?? '').trim()

  return {
    status: STATUS_ENVIO_VALIDOS.has(status) ? status : '',
    correlation_id: correlationId,
    data: /^\d{4}-\d{2}-\d{2}$/.test(data) ? data : '',
    busca,
  }
}

export function possuiFiltroAtivo(filtros = {}) {
  const normalizados = normalizarFiltrosTaskConsole(filtros)
  return Boolean(
    normalizados.status
    || normalizados.bucket
    || normalizados.prioridade
    || normalizados.responsavel
    || normalizados.busca,
  )
}

export function possuiFiltroEnvioAtivo(filtros = {}) {
  const normalizados = normalizarFiltrosEnvioTaskConsole(filtros)
  return Boolean(normalizados.status || normalizados.correlation_id || normalizados.data || normalizados.busca)
}

export function filtrarTarefasTaskConsole(itens = [], filtros = {}) {
  const filtrosNormalizados = normalizarFiltrosTaskConsole(filtros)
  const busca = normalizarTexto(filtrosNormalizados.busca)
  const responsavel = normalizarTexto(filtrosNormalizados.responsavel)
  const bucket = normalizarTexto(filtrosNormalizados.bucket)

  return itens.filter((item) => {
    const statusItem = normalizarTexto(item.status)
    const prioridadeItem = normalizarTexto(item.prioridade)
    const bucketItem = normalizarTexto(item.bucket)
    const responsavelItem = normalizarTexto(item.responsavelEmail)

    const statusOk = !filtrosNormalizados.status || statusItem === filtrosNormalizados.status
    const bucketOk = !bucket || bucketItem.includes(bucket)
    const prioridadeOk = !filtrosNormalizados.prioridade || prioridadeItem === filtrosNormalizados.prioridade
    const responsavelOk = !responsavel || responsavelItem.includes(responsavel)

    const textoBusca = normalizarTexto([
      item.titulo,
      item.descricao,
      item.bucket,
      item.prioridade,
      item.status,
      item.responsavelEmail,
      item.plannerCorrelationId,
    ].join(' '))
    const buscaOk = !busca || textoBusca.includes(busca)

    return statusOk && bucketOk && prioridadeOk && responsavelOk && buscaOk
  })
}

export function filtrarHistoricoEnvios(itens = [], filtros = {}) {
  const filtrosNormalizados = normalizarFiltrosEnvioTaskConsole(filtros)
  const busca = normalizarTexto(filtrosNormalizados.busca)
  const correlationId = normalizarTexto(filtrosNormalizados.correlation_id)

  return itens.filter((item) => {
    const statusItem = normalizarTexto(item.status)
    const dataItem = extrairData(item.enviadoEm)

    const statusOk = !filtrosNormalizados.status || statusItem === filtrosNormalizados.status
    const correlationOk = !correlationId || normalizarTexto(item.correlationId).includes(correlationId)
    const dataOk = !filtrosNormalizados.data || dataItem === filtrosNormalizados.data

    const textoBusca = normalizarTexto([
      item.mensagem,
      item.flow,
      item.correlationId,
      item.status,
      String(item.total),
    ].join(' '))
    const buscaOk = !busca || textoBusca.includes(busca)

    return statusOk && correlationOk && dataOk && buscaOk
  })
}

export function criarQueryFiltrosTaskConsole(filtros = {}) {
  const normalizados = normalizarFiltrosTaskConsole(filtros)
  return Object.fromEntries(
    Object.entries(normalizados).filter(([, valor]) => Boolean(String(valor ?? '').trim())),
  )
}

export function criarQueryFiltrosEnvioTaskConsole(filtros = {}) {
  const normalizados = normalizarFiltrosEnvioTaskConsole(filtros)
  const query = {}
  if (normalizados.status) query.envio_status = normalizados.status
  if (normalizados.correlation_id) query.correlation_id = normalizados.correlation_id
  if (normalizados.data) query.data = normalizados.data
  if (normalizados.busca) query.busca_envio = normalizados.busca
  return query
}

export function criarRegistroEnvioTaskConsole({
  enviado,
  total,
  flow,
  flowId,
  correlationId,
  mensagem,
  erro = '',
}) {
  return {
    id: correlationId || `envio-${Date.now()}`,
    enviadoEm: new Date().toISOString(),
    status: enviado ? 'sucesso' : (total > 0 ? 'parcial' : 'erro'),
    total: Number(total) || 0,
    flow: flow || 'ReqSys - Criar no Planner',
    flowId: flowId || '',
    correlationId: correlationId || '',
    mensagem: mensagem || '',
    erro: String(erro ?? ''),
  }
}

export function contarTarefasTaskConsole(itens = []) {
  return itens.reduce((acc, item) => {
    const status = normalizarTexto(item.status)
    if (status === 'pendente') acc.pendentes += 1
    if (status === 'criada') acc.criadas += 1
    if (status === 'falha') acc.falhas += 1
    return acc
  }, { pendentes: 0, criadas: 0, falhas: 0 })
}

export const TASK_CONSOLE_ENVIOS_KEY = 'reqsys_task_console_envios'

export function carregarHistoricoEnvios(storage = localStorage) {
  try {
    const salvo = JSON.parse(storage.getItem(TASK_CONSOLE_ENVIOS_KEY) || '[]')
    return Array.isArray(salvo) ? salvo : []
  } catch {
    return []
  }
}

export function salvarHistoricoEnvios(itens, storage = localStorage, limite = 40) {
  storage.setItem(TASK_CONSOLE_ENVIOS_KEY, JSON.stringify(itens.slice(0, limite)))
}
