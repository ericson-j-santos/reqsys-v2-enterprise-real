export const DASHBOARD_EMPTY_EVENT = 'reqsys:dashboard-empty-result'

const DASHBOARD_PATHS = ['/dashboard', '/monitoramento', '/analytics', '/estatisticas']

export function extractDashboardRows(payload) {
  const candidates = [
    payload?.items,
    payload?.rows,
    payload?.linhas,
    payload?.data?.items,
    payload?.data?.rows,
    payload?.data?.linhas,
    payload?.resultado?.linhas,
    payload?.data?.resultado?.linhas,
  ]
  return candidates.find(Array.isArray)
}

export function isEmptyDashboardResponse(response = {}) {
  const url = String(response?.config?.url || '')
  const method = String(response?.config?.method || 'get').toLowerCase()
  const rows = extractDashboardRows(response?.data)
  return method === 'get' && DASHBOARD_PATHS.some((path) => url.includes(path)) && Array.isArray(rows) && rows.length === 0
}

export function emitDashboardEmptyResult(response) {
  if (typeof window === 'undefined') return
  const retryConfig = response?.config
  window.dispatchEvent(new CustomEvent(DASHBOARD_EMPTY_EVENT, {
    detail: {
      context: String(retryConfig?.url || 'operational-dashboard').slice(0, 80),
      reason: 'Nenhum registro atende ao período ou aos filtros atuais.',
      retry: retryConfig ? () => import('./api').then(({ api }) => api.request(retryConfig)) : null,
    },
  }))
}
