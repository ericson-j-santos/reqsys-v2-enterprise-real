export const DASHBOARD_CLEAR_FILTERS_EVENT = 'reqsys:dashboard-clear-filters'

const PRIORITY_ROUTES = new Set(['/analytics', '/estatisticas', '/monitoramento-operacional', '/'])

export function clearDashboardFilters(context = 'operational-dashboard') {
  if (typeof window === 'undefined') return false

  const pathname = window.location?.pathname || '/'
  if (!PRIORITY_ROUTES.has(pathname)) {
    window.dispatchEvent(new CustomEvent(DASHBOARD_CLEAR_FILTERS_EVENT, { detail: { context } }))
    return false
  }

  window.history.replaceState({}, '', pathname)
  window.dispatchEvent(new CustomEvent(DASHBOARD_CLEAR_FILTERS_EVENT, {
    detail: { context, route: pathname, cleared: true },
  }))
  return true
}

export function installDashboardFilterReset(handler) {
  if (typeof window === 'undefined' || typeof handler !== 'function') return () => {}
  const listener = (event) => handler(event?.detail || {})
  window.addEventListener(DASHBOARD_CLEAR_FILTERS_EVENT, listener)
  return () => window.removeEventListener(DASHBOARD_CLEAR_FILTERS_EVENT, listener)
}
