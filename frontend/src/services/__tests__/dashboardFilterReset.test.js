import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearDashboardFilters, DASHBOARD_CLEAR_FILTERS_EVENT } from '../dashboardFilterReset'

afterEach(() => {
  window.history.replaceState({}, '', '/')
  vi.restoreAllMocks()
})

describe('dashboardFilterReset', () => {
  it('remove query string nas rotas prioritárias e emite evento', () => {
    window.history.pushState({}, '', '/analytics?periodo=7d&status=erro')
    const listener = vi.fn()
    window.addEventListener(DASHBOARD_CLEAR_FILTERS_EVENT, listener, { once: true })

    expect(clearDashboardFilters('analytics-dashboard')).toBe(true)
    expect(window.location.pathname).toBe('/analytics')
    expect(window.location.search).toBe('')
    expect(listener).toHaveBeenCalledOnce()
  })

  it('mantém comportamento advisory em rota não priorizada', () => {
    window.history.pushState({}, '', '/requisitos?status=aberto')
    expect(clearDashboardFilters('requisitos')).toBe(false)
    expect(window.location.search).toBe('?status=aberto')
  })
})
