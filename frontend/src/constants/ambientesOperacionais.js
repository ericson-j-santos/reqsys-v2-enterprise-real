/** Catálogo canônico de ambientes ReqSys. DEV usa locator assinado -> PC24x7; sem fallback Fly.io. */
export const AMBIENTES_OPERACIONAIS = [
  {
    id: 'local',
    shortId: 'local',
    label: 'Local',
    color: 'grey',
    frontend: 'http://127.0.0.1:5173',
    backend: 'http://127.0.0.1:8000',
    duckdns: '',
    uso: 'Desenvolvimento na máquina (Vite + uvicorn).',
    onlyLocal: true,
  },
  {
    id: 'desenvolvimento',
    shortId: 'dev',
    label: 'Dev',
    color: 'info',
    frontend: 'https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev/',
    backend: 'same-origin:/api',
    duckdns: '',
    uso: 'Evolução e testes técnicos.',
  },
  {
    id: 'homologacao',
    shortId: 'stg',
    label: 'Homolog',
    color: 'warning',
    frontend: 'https://reqsys-app-stg.fly.dev',
    backend: 'https://reqsys-api-stg.fly.dev',
    duckdns: 'https://tierin.duckdns.org',
    uso: 'Validação pré-produção.',
  },
  {
    id: 'producao',
    shortId: 'prod',
    label: 'Prod',
    color: 'success',
    frontend: 'https://reqsys-app.fly.dev',
    backend: 'https://reqsys-api.fly.dev',
    duckdns: 'https://tieriprod.duckdns.org',
    uso: 'Acesso final após implantação.',
  },
]

const ALIAS_AMBIENTE = {
  dev: 'desenvolvimento',
  development: 'desenvolvimento',
  local: 'local',
  stg: 'homologacao',
  staging: 'homologacao',
  homolog: 'homologacao',
  homologacao: 'homologacao',
  hml: 'homologacao',
  prod: 'producao',
  production: 'producao',
  producao: 'producao',
  testes: 'testes',
  test: 'testes',
  e2e_responsivo: 'desenvolvimento',
}

export function normalizarAmbienteId(value) {
  const raw = String(value || '')
    .trim()
    .toLowerCase()
    .replace(/-/g, '_')
  if (!raw) return 'desenvolvimento'
  return ALIAS_AMBIENTE[raw] || raw
}

export function ambientePorId(id) {
  const normalizado = normalizarAmbienteId(id)
  return AMBIENTES_OPERACIONAIS.find((item) => item.id === normalizado || item.shortId === normalizado) || null
}

export function detectarAmbientePorHostname(hostname = '') {
  const host = String(hostname).toLowerCase()
  if (!host || host === 'localhost' || host === '127.0.0.1') return 'local'
  if (host.includes('reqsys-app-stg') || host.includes('tierin.duckdns')) return 'homologacao'
  if (host.endsWith('.trycloudflare.com') || host === 'ericson-j-santos.github.io') return 'desenvolvimento'
  if (host.includes('reqsys-app.fly.dev') || host.includes('tieriprod.duckdns')) return 'producao'
  return null
}

export function resolverAmbienteAtual({ environmentHint = '', hostname = '' } = {}) {
  const porHost = detectarAmbientePorHostname(hostname)
  if (porHost) return porHost
  const normalizado = normalizarAmbienteId(environmentHint)
  if (ambientePorId(normalizado)) return normalizado
  return 'desenvolvimento'
}

export function ambientesNavegaveis({ hostname = '' } = {}) {
  const host = String(hostname).toLowerCase()
  const isLocal = !host || host === 'localhost' || host === '127.0.0.1'
  return AMBIENTES_OPERACIONAIS.filter((item) => !item.onlyLocal || isLocal)
}

export function montarUrlAmbiente(ambiente, { path = '/', preserveRoute = true } = {}) {
  const alvo = typeof ambiente === 'string' ? ambientePorId(ambiente) : ambiente
  if (!alvo?.frontend) return null

  let rota = path
  if (preserveRoute && typeof window !== 'undefined') {
    rota = `${window.location.pathname}${window.location.search}${window.location.hash}`
  }

  const suffix = rota.startsWith('/') ? rota : `/${rota}`
  if (alvo.id === 'desenvolvimento') {
    const locator = new URL(alvo.frontend)
    locator.searchParams.set('target', suffix)
    return locator.toString()
  }

  const base = alvo.frontend.replace(/\/$/, '')
  return `${base}${suffix}`
}

export function ambienteRequerConfirmacao(ambienteId) {
  return normalizarAmbienteId(ambienteId) === 'producao'
}

export function irParaAmbiente(ambienteId, opcoes = {}) {
  const { skipConfirm = false, ...resto } = opcoes
  const url = montarUrlAmbiente(ambienteId, resto)
  if (!url || typeof window === 'undefined') return false

  if (!skipConfirm && ambienteRequerConfirmacao(ambienteId)) {
    const confirmado = window.confirm(
      `Você está prestes a abrir o ambiente de PRODUÇÃO.\n\n${url}\n\nDeseja continuar?`,
    )
    if (!confirmado) return false
  }

  window.location.assign(url)
  return true
}

export function labelAmbiente(id) {
  return ambientePorId(id)?.label || String(id || 'desenvolvimento').replace(/_/g, ' ')
}
