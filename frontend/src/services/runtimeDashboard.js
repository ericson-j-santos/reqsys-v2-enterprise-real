import { mapearCardsComDrilldown } from '../utils/runtimeDrilldown'
import { estadoParaSemaforo } from '../utils/filtrosMonitoramento'

function normalizarEventosTimeline(eventos = []) {
  return eventos.map((evento, index) => ({
    id: evento.id || `${evento.event_type || 'evento'}-${evento.event_at || index}`,
    event_type: evento.event_type,
    status: evento.status,
    severity: evento.severity || (['degraded', 'blocked', 'vermelho'].includes(String(evento.status)) ? 'high' : 'medium'),
    correlation_id: evento.correlation_id,
    occurred_at: evento.occurred_at || evento.event_at,
    spa_drilldown: evento.spa_drilldown,
  }))
}

export async function carregarRuntimeDashboard() {
  const resposta = await fetch('/api/runtime/dashboard', { headers: { Accept: 'application/json' } })
  if (!resposta.ok) throw new Error('Falha ao carregar runtime dashboard')
  const payload = await resposta.json()
  const data = payload.data || null
  if (!data) return null

  const incidentSection = (data.sections || []).find((section) => section.id === 'incident-timeline')
  const incidentEvents = normalizarEventosTimeline(incidentSection?.items || [])

  return {
    ...data,
    cards: mapearCardsComDrilldown(data.cards || []),
    incident_timeline: incidentEvents,
  }
}

export async function carregarRuntimeAnalytics() {
  const resposta = await fetch('/api/runtime/analytics', { headers: { Accept: 'application/json' } })
  if (!resposta.ok) throw new Error('Falha ao carregar runtime analytics')
  const payload = await resposta.json()
  const data = payload.data || {}
  return {
    ...data,
    incident_timeline: normalizarEventosTimeline(data.incident_lifecycle?.events || []),
  }
}

export async function carregarPainelOperacional() {
  const [dashboard, analytics] = await Promise.all([
    carregarRuntimeDashboard(),
    carregarRuntimeAnalytics().catch(() => ({ incident_timeline: [] })),
  ])

  const timeline = dashboard?.incident_timeline?.length
    ? dashboard.incident_timeline
    : analytics.incident_timeline

  return {
    dashboard,
    analytics,
    incident_timeline: timeline,
    correlation_id: dashboard?.correlation_id || analytics?.correlation_id || '',
  }
}

export function formatarValorRuntimeCard(card) {
  if (card.unit === 'seconds') return `${Math.round(card.value)}s`
  if (card.unit === 'percent') return `${card.value}%`
  if (card.unit) return `${card.value} ${card.unit}`
  return card.value
}

export function semaforoRuntimeCard(card) {
  if (card.severity) return estadoParaSemaforo(card.severity)
  if (card.type === 'status') return estadoParaSemaforo(card.value)
  if (card.id === 'risk-score' && Number(card.value) >= 70) return 'vermelho'
  if (card.id === 'risk-score' && Number(card.value) >= 40) return 'amarelo'
  if (card.id === 'pending-items' && Number(card.value) > 0) return 'amarelo'
  return 'verde'
}
