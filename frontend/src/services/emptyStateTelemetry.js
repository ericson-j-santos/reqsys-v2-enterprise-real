const STORAGE_KEY = 'reqsys_empty_state_telemetry'
const ALLOWED_EVENTS = new Set(['view', 'primary_action', 'secondary_action'])

export function recordEmptyState({ context, event }) {
  if (typeof window === 'undefined' || !context || !ALLOWED_EVENTS.has(event)) return
  const entry = {
    context: String(context).slice(0, 80),
    event,
    occurredAt: new Date().toISOString(),
  }
  try {
    const current = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]')
    const items = Array.isArray(current) ? current : []
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify([...items.slice(-49), entry]))
    window.dispatchEvent(new CustomEvent('reqsys:empty-state-telemetry', { detail: entry }))
  } catch {
    // Telemetria de UX não pode interromper a jornada do usuário.
  }
}

export function readEmptyStateTelemetry() {
  if (typeof sessionStorage === 'undefined') return []
  try {
    const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(value) ? value : []
  } catch {
    return []
  }
}

export { STORAGE_KEY }
