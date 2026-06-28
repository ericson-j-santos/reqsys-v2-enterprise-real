import { mapearCardsComDrilldown } from '../utils/runtimeDrilldown'
import { estadoParaSemaforo } from '../utils/filtrosMonitoramento'

export async function carregarRuntimeDashboard() {
  const resposta = await fetch('/api/runtime/dashboard', { headers: { Accept: 'application/json' } })
  if (!resposta.ok) throw new Error('Falha ao carregar runtime dashboard')
  const payload = await resposta.json()
  const data = payload.data || null
  if (!data) return null

  return {
    ...data,
    cards: mapearCardsComDrilldown(data.cards || []),
  }
}

export function formatarValorRuntimeCard(card) {
  if (card.unit === 'seconds') return `${Math.round(card.value)}s`
  if (card.unit === 'percent') return `${card.value}%`
  if (card.unit) return `${card.value} ${card.unit}`
  return card.value
}

export function semaforoRuntimeCard(card) {
  if (card.type === 'governance_evidence') {
    if (card.value === 'implemented') return 'verde'
    if (card.value === 'dry_run') return 'amarelo'
    return 'desconhecido'
  }
  if (card.severity) return estadoParaSemaforo(card.severity)
  if (card.type === 'status') return estadoParaSemaforo(card.value)
  if (card.id === 'risk-score' && Number(card.value) >= 70) return 'vermelho'
  if (card.id === 'risk-score' && Number(card.value) >= 40) return 'amarelo'
  if (card.id === 'pending-items' && Number(card.value) > 0) return 'amarelo'
  return 'verde'
}
