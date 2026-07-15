const STORAGE_KEY = 'reqsys_empty_state_telemetry'
const ALLOWED_EVENTS = new Set(['view', 'primary_action', 'secondary_action', 'recovered'])
const MAX_ITEMS = 100

function readItems() {
  if (typeof sessionStorage === 'undefined') return []
  try {
    const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(value) ? value : []
  } catch {
    return []
  }
}

export function recordEmptyState({ context, event }) {
  if (typeof window === 'undefined' || !context || !ALLOWED_EVENTS.has(event)) return null

  const normalizedContext = String(context).slice(0, 80)
  const occurredAt = new Date().toISOString()
  const items = readItems()
  const entry = { context: normalizedContext, event, occurredAt }

  if (event !== 'view') {
    const lastView = [...items].reverse().find((item) => item?.context === normalizedContext && item?.event === 'view')
    if (lastView?.occurredAt) {
      const durationMs = Date.parse(occurredAt) - Date.parse(lastView.occurredAt)
      if (Number.isFinite(durationMs) && durationMs >= 0) entry.recoveryDurationMs = durationMs
    }
  }

  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify([...items.slice(-(MAX_ITEMS - 1)), entry]))
    window.dispatchEvent(new CustomEvent('reqsys:empty-state-telemetry', { detail: entry }))
    return entry
  } catch {
    // Telemetria de UX não pode interromper a jornada do usuário.
    return null
  }
}

export function readEmptyStateTelemetry() {
  return readItems()
}

export { STORAGE_KEY }
