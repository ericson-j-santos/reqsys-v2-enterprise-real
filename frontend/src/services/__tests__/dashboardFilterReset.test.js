import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearDashboardFilters, DASHBOARD_CLEAR_FILTERS_EVENT } from '../dashboardFilterReset'

const listeners = []

function listenOnce(eventName, listener) {
  window.addEventListener(eventName, listener, { once: true })
  listeners.push([eventName, listener])
}

afterEach(() => {
  for (const [eventName, listener] of listeners.splice(0)) {
    window.removeEventListener(eventName, listener)
  }
  window.history.replaceState({}, '', '/')
  vi.restoreAllMocks()
})

describe('dashboardFilterReset', () => {
  it('remove query string nas rotas prioritárias e emite evento', () => {
    window.history.pushState({}, '', '/analytics?periodo=7d&status=erro')
    const listener = vi.fn()
    listenOnce(DASHBOARD_CLEAR_FILTERS_EVENT, listener)

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
